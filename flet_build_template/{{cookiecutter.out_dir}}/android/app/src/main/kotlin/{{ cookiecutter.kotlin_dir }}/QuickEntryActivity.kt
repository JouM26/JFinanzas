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
    private lateinit var paymentMethodField: Spinner
    private lateinit var accountField: Spinner
    private lateinit var paymentNote: TextView
    private var accountIds: List<Long> = emptyList()
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

        paymentNote = TextView(this).apply {
            text = "Registro rápido · medio de pago: efectivo"
            textSize = 14f
            setTextColor(Color.DKGRAY)
            setPadding(0, dp(6), 0, dp(12))
        }
        root.addView(paymentNote, matchWrap())

        descriptionField = EditText(this).apply {
            hint = "Descripción"
            isSingleLine = true
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
        }
        root.addView(descriptionField, matchWrap())

        categoryField = Spinner(this).apply {
            adapter = ArrayAdapter(this@QuickEntryActivity, android.R.layout.simple_spinner_dropdown_item, CATEGORIES)
            if (isIncome) setSelection(CATEGORIES.indexOf("Salario"))
        }
        root.addView(categoryField, matchWrap())

        val paymentOptions = if (isIncome) {
            arrayOf("Efectivo", "Cuenta bancaria")
        } else {
            arrayOf("Efectivo", "Cuenta bancaria", "Tarjeta de crédito")
        }
        paymentMethodField = Spinner(this).apply {
            adapter = ArrayAdapter(this@QuickEntryActivity, android.R.layout.simple_spinner_dropdown_item, paymentOptions)
        }
        root.addView(paymentMethodField, matchWrap())

        accountField = Spinner(this)
        root.addView(accountField, matchWrap())
        paymentMethodField.onItemSelectedListener = object : android.widget.AdapterView.OnItemSelectedListener {
            override fun onNothingSelected(parent: android.widget.AdapterView<*>?) = Unit
            override fun onItemSelected(parent: android.widget.AdapterView<*>?, view: android.view.View?, position: Int, id: Long) {
                updatePaymentAccountOptions()
            }
        }

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

        val scrollContainer = android.widget.ScrollView(this).apply {
            setBackgroundColor(Color.WHITE)
            isFillViewport = true
            addView(root, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        }
        setContentView(scrollContainer)
        updatePaymentAccountOptions()
        window.setLayout(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
    }

    private fun updatePaymentAccountOptions() {
        val method = selectedPaymentMethod()
        val requiresAccount = method != "efectivo"
        accountField.visibility = if (requiresAccount) android.view.View.VISIBLE else android.view.View.GONE
        paymentNote.text = when (method) {
            "banco" -> "El saldo de la cuenta seleccionada se actualizará al guardar."
            "tarjeta_credito" -> "La compra se agregará a Créditos (1 cuota, sin intereses)."
            else -> "Registro rápido · medio de pago: efectivo"
        }

        if (!requiresAccount) {
            accountIds = emptyList()
            return
        }

        val acceptedType = if (method == "tarjeta_credito") "credito" else null
        val accountNames = mutableListOf<String>()
        val ids = mutableListOf<Long>()
        try {
            openDatabase().use { database ->
                val cursor = if (acceptedType == null) {
                    database.rawQuery(
                        "SELECT id, nombre_banco, tipo_cuenta FROM cuentas_bancarias " +
                            "WHERE activa = 1 AND tipo_cuenta IN ('debito','ahorro','inversion') ORDER BY nombre_banco",
                        null
                    )
                } else {
                    database.rawQuery(
                        "SELECT id, nombre_banco, tipo_cuenta FROM cuentas_bancarias " +
                            "WHERE activa = 1 AND tipo_cuenta = ? ORDER BY nombre_banco",
                        arrayOf(acceptedType)
                    )
                }
                cursor.use {
                    while (it.moveToNext()) {
                        ids.add(it.getLong(0))
                        accountNames.add("${it.getString(1)} (${it.getString(2)})")
                    }
                }
            }
            accountIds = ids
            accountField.adapter = ArrayAdapter(
                this,
                android.R.layout.simple_spinner_dropdown_item,
                if (accountNames.isEmpty()) listOf("No hay cuentas registradas") else accountNames
            )
            if (accountNames.isEmpty()) {
                paymentNote.text = if (method == "tarjeta_credito") {
                    "Registra primero una tarjeta de crédito en la app."
                } else {
                    "Registra primero una cuenta bancaria en la app."
                }
            }
        } catch (exception: Exception) {
            accountIds = emptyList()
            paymentNote.text = "No se pudieron cargar las cuentas: ${exception.localizedMessage}"
        }
    }

    private fun selectedPaymentMethod(): String = when (paymentMethodField.selectedItemPosition) {
        1 -> "banco"
        2 -> "tarjeta_credito"
        else -> "efectivo"
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
            val method = selectedPaymentMethod()
            if (movementType == "ingreso" && method == "tarjeta_credito") {
                error("Los ingresos no se pueden registrar con tarjeta de crédito")
            }
            val accountId = if (method == "efectivo") null else accountIds.getOrNull(accountField.selectedItemPosition)
            if (method != "efectivo" && accountId == null) {
                error("Selecciona una cuenta registrada para este medio de pago")
            }

            database = openDatabase()
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

            var accountName: String? = null
            var accountType: String? = null
            var currentBalance = 0.0
            var creditLimit = 0.0
            if (accountId != null) {
                val cursor = database.rawQuery(
                    "SELECT nombre_banco, tipo_cuenta, COALESCE(saldo, 0), COALESCE(limite_credito, 0) " +
                        "FROM cuentas_bancarias WHERE id = ? AND activa = 1",
                    arrayOf(accountId.toString())
                )
                cursor.use {
                    if (!it.moveToFirst()) error("La cuenta seleccionada ya no está disponible")
                    accountName = it.getString(0)
                    accountType = it.getString(1)
                    currentBalance = it.getDouble(2)
                    creditLimit = it.getDouble(3)
                }
                if (method == "tarjeta_credito" && accountType != "credito") {
                    error("Selecciona una tarjeta de crédito registrada")
                }
                if (method == "banco" && accountType == "credito") {
                    error("Para pagar con tarjeta, selecciona Tarjeta de crédito")
                }
                if (method == "tarjeta_credito" && creditLimit > 0 && kotlin.math.abs(currentBalance) + amount > creditLimit) {
                    error("El gasto supera el crédito disponible de esta tarjeta")
                }
            }

            val values = ContentValues().apply {
                put("tipo", movementType)
                put("categoria", categoryField.selectedItem?.toString() ?: "Otro")
                put("monto", amount)
                put("descripcion", description)
                put("fecha", SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault()).format(Date()))
                put("medio_pago", method)
                if (accountId == null) putNull("cuenta_bancaria_id") else put("cuenta_bancaria_id", accountId)
            }
            database.beginTransaction()
            try {
                val movementId = database.insertOrThrow("movimientos", null, values)
                if (accountId != null && method == "banco") {
                    val delta = if (movementType == "ingreso") amount else -amount
                    database.execSQL(
                        "UPDATE cuentas_bancarias SET saldo = COALESCE(saldo, 0) + ? WHERE id = ?",
                        arrayOf(delta, accountId)
                    )
                } else if (accountId != null && method == "tarjeta_credito") {
                    database.execSQL(
                        "UPDATE cuentas_bancarias SET saldo = -ABS(COALESCE(saldo, 0)) - ? WHERE id = ?",
                        arrayOf(amount, accountId)
                    )
                    val date = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())
                    database.execSQL(
                        "INSERT INTO creditos " +
                            "(descripcion, banco, monto_total, meses_sin_intereses, cuota_mensual, " +
                            "fecha_compra, tasa_interes, cuenta_bancaria_id, movimiento_id) " +
                            "VALUES (?, ?, ?, 1, ?, ?, 0, ?, ?)",
                        arrayOf(description, accountName, amount, amount, date, accountId, movementId)
                    )
                    val creditId = database.rawQuery("SELECT last_insert_rowid()", null).use {
                        if (it.moveToFirst()) it.getLong(0) else error("No se pudo crear el registro de crédito")
                    }
                    database.execSQL(
                        "UPDATE movimientos SET credito_id = ? WHERE id = ?",
                        arrayOf(creditId, movementId)
                    )
                }
                database.setTransactionSuccessful()
            } finally {
                database.endTransaction()
            }
            val paymentLabel = when (method) {
                "banco" -> "en cuenta bancaria"
                "tarjeta_credito" -> "en Créditos"
                else -> "en efectivo"
            }
            Toast.makeText(
                this,
                "${if (movementType == "ingreso") "Ingreso" else "Gasto"} guardado $paymentLabel",
                Toast.LENGTH_SHORT
            ).show()
            finish()
        } catch (exception: Exception) {
            Toast.makeText(this, "No se pudo guardar: ${exception.localizedMessage}", Toast.LENGTH_LONG).show()
        } finally {
            database?.close()
        }
    }

    private fun openDatabase(): SQLiteDatabase {
        // Serious Python ejecuta la app desde application-support/data;
        // en Android ese directorio corresponde a filesDir/data.
        val dataDirectory = File(filesDir, "data")
        if (!dataDirectory.exists() && !dataDirectory.mkdirs()) {
            error("No se pudo preparar el almacenamiento de la app")
        }
        val database = SQLiteDatabase.openOrCreateDatabase(File(dataDirectory, "finanzas.db"), null)
        // PRAGMA devuelve una fila y debe ejecutarse con rawQuery, no execSQL.
        database.rawQuery("PRAGMA busy_timeout=10000", null).use { it.moveToFirst() }
        return database
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
