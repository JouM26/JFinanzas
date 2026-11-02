package {{ cookiecutter.org_name_2 }}.{{ cookiecutter.package_name }}

import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.ComponentName
import android.content.Intent
import android.app.PendingIntent
import android.database.sqlite.SQLiteDatabase
import android.widget.RemoteViews
import java.io.File
import java.text.NumberFormat
import java.util.Locale
import java.util.concurrent.Executors

/** Widget de consulta rápida: gasto diario, semanal, mensual y ahorro acumulado. */
class FinanceSummaryWidgetProvider : AppWidgetProvider() {
    companion object {
        private val refreshExecutor = Executors.newSingleThreadExecutor()

        fun requestRefresh(context: Context) {
            val manager = AppWidgetManager.getInstance(context)
            val component = ComponentName(context, FinanceSummaryWidgetProvider::class.java)
            val ids = manager.getAppWidgetIds(component)
            if (ids.isEmpty()) return
            context.sendBroadcast(Intent(AppWidgetManager.ACTION_APPWIDGET_UPDATE).apply {
                this.component = component
                putExtra(AppWidgetManager.EXTRA_APPWIDGET_IDS, ids)
            })
        }
    }

    override fun onReceive(context: Context, intent: Intent) {
        super.onReceive(context, intent)
        if (intent.action == Intent.ACTION_MY_PACKAGE_REPLACED) {
            requestRefresh(context)
        }
    }

    override fun onUpdate(
        context: Context,
        manager: AppWidgetManager,
        appWidgetIds: IntArray
    ) {
        // Leer SQLite y buscar la ruta de datos puede tardar. No bloquear el
        // hilo principal del proceso, especialmente durante el arranque.
        val pendingResult = goAsync()
        refreshExecutor.execute {
            try {
                updateWidgets(context.applicationContext, manager, appWidgetIds)
            } catch (_: Exception) {
                // Un widget sin datos no debe tumbar el proceso de la aplicación.
            } finally {
                pendingResult.finish()
            }
        }
    }

    private fun updateWidgets(context: Context, manager: AppWidgetManager, appWidgetIds: IntArray) {
        val totals = loadTotals(context)
        appWidgetIds.forEach { id ->
            val views = RemoteViews(context.packageName, R.layout.finance_summary_widget).apply {
                setTextViewText(R.id.summary_today, "Hoy\n${formatMoney(totals[0])}")
                setTextViewText(R.id.summary_week, "Semana\n${formatMoney(totals[1])}")
                val monthStatus = if (totals[4] > 0) {
                    "Mes\n${formatMoney(totals[2])} / ${formatMoney(totals[4])}"
                } else {
                    "Mes\n${formatMoney(totals[2])}"
                }
                setTextViewText(R.id.summary_month, monthStatus)
                setTextViewText(R.id.summary_savings, "Ahorro\n${formatMoney(totals[3])}")
                val openApp = PendingIntent.getActivity(
                    context,
                    id,
                    context.packageManager.getLaunchIntentForPackage(context.packageName)
                        ?: Intent(context, MainActivity::class.java),
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
                )
                setOnClickPendingIntent(R.id.summary_widget_root, openApp)
            }
            manager.updateAppWidget(id, views)
        }
    }

    private fun loadTotals(context: Context): DoubleArray {
        registeredDatabaseFile(context)?.let { return loadTotalsFromFile(it) }
        val canonical = File(context.filesDir, "app_flutter/finanzas.db")
        val candidates = linkedSetOf(
            canonical,
            File(context.filesDir, "data/finanzas.db"),
            File(context.filesDir, "flet/py/data/finanzas.db"),
            File(context.filesDir, "flet/data/finanzas.db"),
            File(context.filesDir, "flet/py/finanzas.db"),
        )
        try {
            (context.filesDir.parentFile ?: context.filesDir).walkTopDown().maxDepth(9).filter {
                it.isFile && it.name == "finanzas.db"
            }.forEach { candidates.add(it) }
        } catch (_: Exception) { }

        val mejores = candidates.filter { it.isFile }.mapNotNull { candidate ->
            try {
                SQLiteDatabase.openDatabase(candidate.absolutePath, null, SQLiteDatabase.OPEN_READONLY).use { db ->
                    Triple(candidate, databaseScore(db), candidate.lastModified())
                }
            } catch (_: Exception) { null }
        }
        val file = mejores.maxWithOrNull(
            compareBy<Triple<File, Long, Long>> { it.second }.thenBy { it.third }
        )?.first ?: return DoubleArray(5)

        return loadTotalsFromFile(file)
    }

    private fun registeredDatabaseFile(context: Context): File? {
        val marker = try {
            (context.filesDir.parentFile ?: context.filesDir).walkTopDown().maxDepth(9)
                .firstOrNull { it.isFile && it.name == "jfinanzas_db_path.txt" }
        } catch (_: Exception) {
            null
        } ?: return null
        return try {
            val file = File(marker.readText().trim()).takeIf { it.isFile } ?: return null
            val score = SQLiteDatabase.openDatabase(file.absolutePath, null, SQLiteDatabase.OPEN_READONLY).use {
                databaseScore(it)
            }
            file.takeIf { score > 0L }
        } catch (_: Exception) {
            null
        }
    }

    private fun databaseScore(db: SQLiteDatabase): Long =
        countRows(db, "movimientos") * 1_000L +
            countRows(db, "cuentas_bancarias", "activa = 1") * 100L +
            countRows(db, "creditos") * 20L + countRows(db, "ahorros") * 10L +
            countRows(db, "presupuestos") * 5L + countRows(db, "transferencias") * 5L

    private fun loadTotalsFromFile(file: File): DoubleArray {
        return try {
            SQLiteDatabase.openDatabase(file.absolutePath, null, SQLiteDatabase.OPEN_READONLY).use { db ->
                db.rawQuery("PRAGMA busy_timeout=5000", null).use { it.moveToFirst() }
                doubleArrayOf(
                    sum(db, "SELECT COALESCE(SUM(monto), 0) FROM movimientos WHERE tipo='gasto' AND date(fecha)=date('now','localtime')"),
                    sum(db, "SELECT COALESCE(SUM(monto), 0) FROM movimientos WHERE tipo='gasto' AND date(fecha)>=date('now','localtime','weekday 0','-6 days') AND date(fecha)<=date('now','localtime')"),
                    sum(db, "SELECT COALESCE(SUM(monto), 0) FROM movimientos WHERE tipo='gasto' AND strftime('%Y-%m',fecha)=strftime('%Y-%m','now','localtime')"),
                    sum(db, "SELECT COALESCE(SUM(monto_actual), 0) FROM ahorros"),
                    sum(db, "SELECT COALESCE(SUM(limite), 0) FROM presupuestos"),
                )
            }
        } catch (_: Exception) { DoubleArray(5) }
    }

    private fun countRows(db: SQLiteDatabase, table: String, condition: String = ""): Long {
        val exists = db.rawQuery(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", arrayOf(table)
        ).use { it.moveToFirst() }
        if (!exists) return 0L
        val where = if (condition.isBlank()) "" else " WHERE $condition"
        return db.rawQuery("SELECT COUNT(*) FROM $table$where", null).use {
            if (it.moveToFirst()) it.getLong(0) else 0L
        }
    }

    private fun sum(db: SQLiteDatabase, query: String): Double = try {
        db.rawQuery(query, null).use { if (it.moveToFirst()) it.getDouble(0) else 0.0 }
    } catch (_: Exception) { 0.0 }

    private fun formatMoney(value: Double): String {
        val amount = kotlin.math.abs(value)
        val (scaled, suffix) = when {
            amount >= 1_000_000 -> value / 1_000_000.0 to "M"
            amount >= 10_000 -> value / 1_000.0 to "k"
            else -> value to ""
        }
        val number = NumberFormat.getNumberInstance(Locale.US).apply {
            maximumFractionDigits = if (suffix.isEmpty()) 0 else 1
            minimumFractionDigits = 0
        }.format(scaled)
        return "\$$number$suffix"
    }
}
