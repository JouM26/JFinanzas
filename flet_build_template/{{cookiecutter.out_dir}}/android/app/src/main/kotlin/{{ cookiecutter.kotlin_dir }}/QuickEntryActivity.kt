package {{ cookiecutter.org_name_2 }}.{{ cookiecutter.package_name }}

import android.app.Activity
import android.content.ContentValues
import android.graphics.Color
import android.os.Bundle
import android.text.InputType
import android.text.Editable
import android.text.TextWatcher
import android.view.Gravity
import android.view.ViewGroup
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast
import android.database.sqlite.SQLiteDatabase
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Formulario pequeño y nativo lanzado desde el widget, sin abrir la pantalla Flet. */
class QuickEntryActivity : Activity() {
    companion object {
        const val EXTRA_TYPE = "jfinanzas.quick_entry.type"
        private val CATEGORIES = arrayOf(
            "Comida", "Transporte", "Servicios", "Ocio", "Salud",
            "Salario", "Compras", "Educación", "Otro"
        )
    }

    private lateinit var descriptionField: EditText
    private lateinit var amountField: EditText
    private lateinit var categoryField: Spinner
    private var movementType: String = "gasto"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        movementType = intent.getStringExtra(EXTRA_TYPE)
            ?.takeIf { it == "ingreso" || it == "gasto" } ?: "gasto"

        val isIncome = movementType == "ingreso"
        val accent = if (isIncome) Color.rgb(46, 125, 50) else Color.rgb(198, 40, 40)
        val padding = dp(22)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(padding, padding, padding, padding)
            setBackgroundColor(Color.WHITE)
        }

        val title = TextView(this).apply {
            text = if (isIncome) "+  Registrar ingreso" else "−  Registrar gasto"
            textSize = 23f
            setTextColor(accent)
            gravity = Gravity.CENTER_VERTICAL
        }
        root.addView(title, matchWrap())

        val note = TextView(this).apply {
            text = "Registro rápido · medio de pago: efectivo"
            textSize = 14f
            setTextColor(Color.DKGRAY)
            setPadding(0, dp(6), 0, dp(12))
        }
        root.addView(note, matchWrap())

        descriptionField = EditText(this).apply {
            hint = "Descripción"
            isSingleLine = true
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
        }
        root.addView(descriptionField, matchWrap())

        categoryField = Spinner(this).apply {
            adapter = ArrayAdapter(this@QuickEntryActivity, android.R.layout.simple_spinner_dropdown_item, CATEGORIES)
        }
        root.addView(categoryField, matchWrap())

        amountField = EditText(this).apply {
            hint = "Monto"
            isSingleLine = true
            inputType = InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_FLAG_DECIMAL
            addTextChangedListener(object : TextWatcher {
                private var formatting = false

                override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
                override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) = Unit

                override fun afterTextChanged(editable: Editable?) {
                    if (formatting || editable == null) return
                    val current = editable.toString()
                    val cursor = this@apply.selectionStart.coerceAtLeast(0).coerceAtMost(current.length)
                    val digitsBeforeCursor = current.substring(0, cursor).count { it.isDigit() }
                    val normalized = current.replace(",", "")
                    val parts = normalized.split('.', limit = 2)
                    val integer = parts[0].filter { it.isDigit() }
                    val grouped = integer.reversed().chunked(3).joinToString(",").reversed()
                    val formatted = grouped + if (parts.size > 1) "." + parts[1].filter { it.isDigit() } else ""
                    if (formatted != current) {
                        formatting = true
                        this@apply.setText(formatted)
                        var newCursor = 0
                        var seenDigits = 0
                        while (newCursor < formatted.length && seenDigits < digitsBeforeCursor) {
                            if (formatted[newCursor].isDigit()) seenDigits++
                            newCursor++
                        }
                        this@apply.setSelection(newCursor.coerceAtMost(formatted.length))
                        formatting = false
                    }
                }
            })
        }
        root.addView(amountField, matchWrap())

        val actions = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.END
        }
        val cancel = Button(this).apply {
            text = "Cancelar"
            setOnClickListener { finish() }
        }
        val save = Button(this).apply {
            text = "Guardar"
            setTextColor(Color.WHITE)
            setBackgroundColor(accent)
            setOnClickListener { saveMovement() }
        }
        actions.addView(cancel)
        actions.addView(save)
        root.addView(actions, matchWrap())

        setContentView(root)
        window.setLayout(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
    }

    private fun saveMovement() {
        val rawAmount = amountField.text.toString().trim().replace(",", "")
        val amount = rawAmount.toDoubleOrNull()
        if (amount == null || amount <= 0.0 || amount.isNaN() || amount.isInfinite()) {
            amountField.error = "Ingresa un monto mayor que cero"
            return
        }
        val description = descriptionField.text.toString().trim()
        if (description.isEmpty()) {
            descriptionField.error = "Escribe una descripción"
            return
        }

        var database: SQLiteDatabase? = null
        try {
            // Serious Python ejecuta la app desde application-support/data;
            // en Android ese directorio corresponde a filesDir/data.
            val dataDirectory = File(filesDir, "data")
            if (!dataDirectory.exists() && !dataDirectory.mkdirs()) {
                error("No se pudo preparar el almacenamiento de la app")
            }
            val databaseFile = File(dataDirectory, "finanzas.db")
            database = SQLiteDatabase.openOrCreateDatabase(databaseFile, null)
            database.execSQL("PRAGMA busy_timeout=10000")
            database.execSQL(
                "CREATE TABLE IF NOT EXISTS movimientos (" +
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, categoria TEXT, " +
                    "monto REAL, descripcion TEXT, fecha TEXT, " +
                    "medio_pago TEXT NOT NULL DEFAULT 'efectivo', " +
                    "cuenta_bancaria_id INTEGER, credito_id INTEGER)"
            )
            ensureMovementColumn(database, "medio_pago", "TEXT")
            ensureMovementColumn(database, "cuenta_bancaria_id", "INTEGER")
            ensureMovementColumn(database, "credito_id", "INTEGER")

            val values = ContentValues().apply {
                put("tipo", movementType)
                put("categoria", categoryField.selectedItem?.toString() ?: "Otro")
                put("monto", amount)
                put("descripcion", description)
                put("fecha", SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault()).format(Date()))
                put("medio_pago", "efectivo")
            }
            database.beginTransaction()
            try {
                database.insertOrThrow("movimientos", null, values)
                database.setTransactionSuccessful()
            } finally {
                database.endTransaction()
            }
            Toast.makeText(this, if (movementType == "ingreso") "Ingreso guardado" else "Gasto guardado", Toast.LENGTH_SHORT).show()
            finish()
        } catch (exception: Exception) {
            Toast.makeText(this, "No se pudo guardar: ${exception.localizedMessage}", Toast.LENGTH_LONG).show()
        } finally {
            database?.close()
        }
    }

    private fun matchWrap() = LinearLayout.LayoutParams(
        ViewGroup.LayoutParams.MATCH_PARENT,
        ViewGroup.LayoutParams.WRAP_CONTENT
    ).apply { bottomMargin = dp(10) }

    private fun ensureMovementColumn(database: SQLiteDatabase, name: String, type: String) {
        val cursor = database.rawQuery("PRAGMA table_info(movimientos)", null)
        val exists = try {
            val nameIndex = cursor.getColumnIndexOrThrow("name")
            var found = false
            while (cursor.moveToNext()) {
                if (cursor.getString(nameIndex) == name) {
                    found = true
                    break
                }
            }
            found
        } finally {
            cursor.close()
        }
        if (!exists) database.execSQL("ALTER TABLE movimientos ADD COLUMN $name $type")
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()
}
