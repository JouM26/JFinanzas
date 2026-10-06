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
        val money = NumberFormat.getNumberInstance(Locale.US).apply { maximumFractionDigits = 0 }
        appWidgetIds.forEach { id ->
            val views = RemoteViews(context.packageName, R.layout.finance_summary_widget).apply {
                setTextViewText(R.id.summary_today, "Hoy gastado\n\$${money.format(totals[0])}")
                setTextViewText(R.id.summary_week, "Esta semana\n\$${money.format(totals[1])}")
                val monthStatus = if (totals[4] > 0) {
                    "Mes: \$${money.format(totals[2])}\n${(totals[2] / totals[4] * 100).toInt()}% del límite"
                } else {
                    "Mes: \$${money.format(totals[2])}\nSin límite definido"
                }
                setTextViewText(R.id.summary_month, monthStatus)
                setTextViewText(R.id.summary_savings, "Ahorros\n\$${money.format(totals[3])}")
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
        val candidates = linkedSetOf(
            File(context.filesDir, "data/finanzas.db"),
            File(context.filesDir, "flet/py/data/finanzas.db"),
            File(context.filesDir, "flet/data/finanzas.db"),
            File(context.filesDir, "flet/py/finanzas.db"),
        )
        try {
            context.filesDir.walkTopDown().maxDepth(7).filter {
                it.isFile && it.name == "finanzas.db"
            }.forEach { candidates.add(it) }
        } catch (_: Exception) { }

        val file = candidates.filter { it.isFile }.maxByOrNull { candidate ->
            try {
                SQLiteDatabase.openDatabase(candidate.absolutePath, null, SQLiteDatabase.OPEN_READONLY).use { db ->
                    countRows(db, "cuentas_bancarias") * 1_000_000L + countRows(db, "movimientos") * 1_000L + candidate.length()
                }
            } catch (_: Exception) { -1L }
        } ?: return DoubleArray(5)

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

    private fun countRows(db: SQLiteDatabase, table: String): Long {
        val exists = db.rawQuery(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", arrayOf(table)
        ).use { it.moveToFirst() }
        if (!exists) return 0L
        return db.rawQuery("SELECT COUNT(*) FROM $table", null).use {
            if (it.moveToFirst()) it.getLong(0) else 0L
        }
    }

    private fun sum(db: SQLiteDatabase, query: String): Double = try {
        db.rawQuery(query, null).use { if (it.moveToFirst()) it.getDouble(0) else 0.0 }
    } catch (_: Exception) { 0.0 }
}
