import flet as ft
import sqlite3
import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
import os

# --- Lógica de Base de Datos (SQLite) ---
class Database:
    def __init__(self):
        self.conn = sqlite3.connect("finanzas.db", check_same_thread=False)
        self.create_table()

    def create_table(self):
        cursor = self.conn.cursor()
        # Tabla de movimientos (solo personal)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT,          -- 'ingreso' o 'gasto'
                categoria TEXT,
                monto REAL,
                descripcion TEXT,
                fecha TEXT
            )
        """)
        # Tabla de suscripciones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS suscripciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                monto REAL NOT NULL,
                dia_cobro INTEGER,  -- día del mes (1-31)
                activa INTEGER DEFAULT 1  -- 1=activa, 0=inactiva
            )
        """)
        # Tabla de préstamos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prestamos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                banco TEXT NOT NULL,
                monto_total REAL NOT NULL,
                monto_pagado REAL DEFAULT 0,
                cuota_mensual REAL NOT NULL,
                dia_pago INTEGER,  -- día del mes (1-31)
                fecha_inicio TEXT,
                activo INTEGER DEFAULT 1  -- 1=activo, 0=pagado
            )
        """)
        # Tabla de ahorros
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ahorros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                meta REAL NOT NULL,
                monto_actual REAL DEFAULT 0,
                fecha_inicio TEXT,
                completado INTEGER DEFAULT 0  -- 1=completado, 0=en progreso
            )
        """)
        # Tabla de compras a crédito
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS creditos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                descripcion TEXT NOT NULL,
                banco TEXT NOT NULL,
                monto_total REAL NOT NULL,
                meses_sin_intereses INTEGER NOT NULL,
                cuota_mensual REAL NOT NULL,
                meses_pagados INTEGER DEFAULT 0,
                fecha_compra TEXT,
                tasa_interes REAL DEFAULT 0,  -- tasa de interés mensual (0 = sin intereses)
                pagado INTEGER DEFAULT 0  -- 1=pagado, 0=en proceso
            )
        """)
        # Tabla de cuentas bancarias
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cuentas_bancarias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_banco TEXT NOT NULL,
                tipo_cuenta TEXT NOT NULL,  -- 'debito', 'credito', 'ahorro', 'inversion'
                saldo REAL DEFAULT 0,
                limite_credito REAL DEFAULT 0,  -- para tarjetas de crédito
                fecha_creacion TEXT,
                activa INTEGER DEFAULT 1  -- 1=activa, 0=inactiva
            )
        """)
        self.conn.commit()

    def agregar_movimiento(self, tipo, categoria, monto, descripcion):
        try:
            cursor = self.conn.cursor()
            fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            cursor.execute("INSERT INTO movimientos (tipo, categoria, monto, descripcion, fecha) VALUES (?, ?, ?, ?, ?)",
                           (tipo, categoria, monto, descripcion, fecha))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error al agregar movimiento: {e}")
            return False

    def obtener_movimientos(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM movimientos ORDER BY id DESC")
            return cursor.fetchall()
        except Exception as e:
            print(f"Error al obtener movimientos: {e}")
            return []

    def obtener_balance(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT tipo, monto FROM movimientos")
            datos = cursor.fetchall()
            
            ingresos = sum(d[1] for d in datos if d[0] == 'ingreso')
            gastos = sum(d[1] for d in datos if d[0] == 'gasto')
            return ingresos, gastos, (ingresos - gastos)
        except Exception as e:
            print(f"Error al obtener balance: {e}")
            return 0, 0, 0
    
    def obtener_balance_mensual(self, mes, anio):
        """Obtiene balance de un mes específico"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT tipo, monto FROM movimientos 
                WHERE strftime('%m', fecha) = ? AND strftime('%Y', fecha) = ?
            """, (f"{mes:02d}", str(anio)))
            datos = cursor.fetchall()
            
            ingresos = sum(d[1] for d in datos if d[0] == 'ingreso')
            gastos = sum(d[1] for d in datos if d[0] == 'gasto')
            return ingresos, gastos
        except Exception as e:
            print(f"Error al obtener balance mensual: {e}")
            return 0, 0
    
    def obtener_movimientos_mensuales(self, mes, anio):
        """Obtiene todos los movimientos de un mes específico"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT id, tipo, categoria, monto, descripcion, fecha 
                FROM movimientos 
                WHERE strftime('%m', fecha) = ? AND strftime('%Y', fecha) = ?
                ORDER BY fecha DESC
            """, (f"{mes:02d}", str(anio)))
            return cursor.fetchall()
        except Exception as e:
            print(f"Error al obtener movimientos mensuales: {e}")
            return []
    
    # --- Métodos para Suscripciones ---
    
    def agregar_suscripcion(self, nombre, monto, dia_cobro):
        try:
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO suscripciones (nombre, monto, dia_cobro) VALUES (?, ?, ?)",
                           (nombre, monto, dia_cobro))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error al agregar suscripción: {e}")
            return False
    
    def obtener_suscripciones(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM suscripciones WHERE activa = 1 ORDER BY dia_cobro")
            return cursor.fetchall()
        except Exception as e:
            print(f"Error al obtener suscripciones: {e}")
            return []
    
    def obtener_total_suscripciones(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT SUM(monto) FROM suscripciones WHERE activa = 1")
            result = cursor.fetchone()[0]
            return result if result else 0
        except Exception as e:
            print(f"Error al obtener total de suscripciones: {e}")
            return 0
    
    def borrar_suscripcion(self, id_suscripcion):
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE suscripciones SET activa = 0 WHERE id = ?", (id_suscripcion,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error al borrar suscripción: {e}")
            return False

    def borrar_movimiento(self, id_movimiento):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM movimientos WHERE id = ?", (id_movimiento,))
        self.conn.commit()
    
    # --- Métodos para Préstamos ---
    
    def agregar_prestamo(self, banco, monto_total, cuota_mensual, dia_pago):
        try:
            cursor = self.conn.cursor()
            fecha_inicio = datetime.datetime.now().strftime("%Y-%m-%d")
            cursor.execute("INSERT INTO prestamos (banco, monto_total, cuota_mensual, dia_pago, fecha_inicio) VALUES (?, ?, ?, ?, ?)",
                           (banco, monto_total, cuota_mensual, dia_pago, fecha_inicio))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error al agregar préstamo: {e}")
            return False
    
    def obtener_prestamos(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM prestamos WHERE activo = 1 ORDER BY dia_pago")
            return cursor.fetchall()
        except Exception as e:
            print(f"Error al obtener préstamos: {e}")
            return []
    
    def obtener_total_cuotas_prestamos(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT SUM(cuota_mensual) FROM prestamos WHERE activo = 1")
            result = cursor.fetchone()[0]
            return result if result else 0
        except Exception as e:
            print(f"Error al obtener total de cuotas: {e}")
            return 0
    
    def obtener_deuda_total(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT SUM(monto_total - monto_pagado) FROM prestamos WHERE activo = 1")
            result = cursor.fetchone()[0]
            return result if result else 0
        except Exception as e:
            print(f"Error al obtener deuda total: {e}")
            return 0
    
    def registrar_pago_prestamo(self, id_prestamo, monto_pago):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT monto_total, monto_pagado FROM prestamos WHERE id = ?", (id_prestamo,))
            result = cursor.fetchone()
            if result:
                monto_total, monto_pagado = result
                nuevo_monto_pagado = monto_pagado + monto_pago
                
                # Si se pagó todo, marcar como inactivo
                if nuevo_monto_pagado >= monto_total:
                    cursor.execute("UPDATE prestamos SET monto_pagado = ?, activo = 0 WHERE id = ?", 
                                   (monto_total, id_prestamo))
                else:
                    cursor.execute("UPDATE prestamos SET monto_pagado = ? WHERE id = ?", 
                                   (nuevo_monto_pagado, id_prestamo))
                self.conn.commit()
                return True
        except Exception as e:
            print(f"Error al registrar pago: {e}")
            return False
    
    def borrar_prestamo(self, id_prestamo):
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE prestamos SET activo = 0 WHERE id = ?", (id_prestamo,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error al borrar préstamo: {e}")
            return False
    
    # --- Métodos para Ahorros ---
    
    def agregar_ahorro(self, nombre, meta):
        try:
            cursor = self.conn.cursor()
            fecha_inicio = datetime.datetime.now().strftime("%Y-%m-%d")
            cursor.execute("INSERT INTO ahorros (nombre, meta, fecha_inicio) VALUES (?, ?, ?)",
                           (nombre, meta, fecha_inicio))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error al agregar ahorro: {e}")
            return False
    
    def obtener_ahorros(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM ahorros WHERE completado = 0 ORDER BY fecha_inicio DESC")
            return cursor.fetchall()
        except Exception as e:
            print(f"Error al obtener ahorros: {e}")
            return []
    
    def obtener_total_ahorros(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT SUM(monto_actual) FROM ahorros WHERE completado = 0")
            result = cursor.fetchone()[0]
            return result if result else 0
        except Exception as e:
            print(f"Error al obtener total de ahorros: {e}")
            return 0
    
    def agregar_monto_ahorro(self, id_ahorro, monto):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT meta, monto_actual FROM ahorros WHERE id = ?", (id_ahorro,))
            result = cursor.fetchone()
            if result:
                meta, monto_actual = result
                nuevo_monto = monto_actual + monto
                
                # Si se alcanzó la meta, marcar como completado
                if nuevo_monto >= meta:
                    cursor.execute("UPDATE ahorros SET monto_actual = ?, completado = 1 WHERE id = ?", 
                                   (meta, id_ahorro))
                else:
                    cursor.execute("UPDATE ahorros SET monto_actual = ? WHERE id = ?", 
                                   (nuevo_monto, id_ahorro))
                self.conn.commit()
                return True
        except Exception as e:
            print(f"Error al agregar monto: {e}")
            return False
    
    def retirar_monto_ahorro(self, id_ahorro, monto):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT monto_actual FROM ahorros WHERE id = ?", (id_ahorro,))
            result = cursor.fetchone()
            if result:
                monto_actual = result[0]
                nuevo_monto = max(0, monto_actual - monto)
                cursor.execute("UPDATE ahorros SET monto_actual = ? WHERE id = ?", 
                               (nuevo_monto, id_ahorro))
                self.conn.commit()
                return True
        except Exception as e:
            print(f"Error al retirar monto: {e}")
            return False
    
    def borrar_ahorro(self, id_ahorro):
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE ahorros SET completado = 1 WHERE id = ?", (id_ahorro,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error al borrar ahorro: {e}")
            return False
    
    # --- Métodos para Compras a Crédito ---
    
    def agregar_credito(self, descripcion, banco, monto_total, meses_plazo, tasa_interes=0):
        try:
            cursor = self.conn.cursor()
            # Si hay interés, calcular cuota con fórmula de amortización
            if tasa_interes > 0:
                tasa_mensual = tasa_interes / 100  # Convertir a decimal
                # Fórmula de cuota fija: P * [r(1+r)^n] / [(1+r)^n - 1]
                cuota_mensual = monto_total * (tasa_mensual * pow(1 + tasa_mensual, meses_plazo)) / (pow(1 + tasa_mensual, meses_plazo) - 1)
            else:
                # Sin intereses, dividir en partes iguales
                cuota_mensual = monto_total / meses_plazo if meses_plazo > 0 else monto_total
            
            fecha_compra = datetime.datetime.now().strftime("%Y-%m-%d")
            cursor.execute("INSERT INTO creditos (descripcion, banco, monto_total, meses_sin_intereses, cuota_mensual, fecha_compra, tasa_interes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (descripcion, banco, monto_total, meses_plazo, cuota_mensual, fecha_compra, tasa_interes))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error al agregar crédito: {e}")
            return False
    
    def obtener_creditos(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM creditos WHERE pagado = 0 ORDER BY fecha_compra DESC")
            return cursor.fetchall()
        except Exception as e:
            print(f"Error al obtener créditos: {e}")
            return []
    
    def obtener_total_cuotas_creditos(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT SUM(cuota_mensual) FROM creditos WHERE pagado = 0")
            result = cursor.fetchone()[0]
            return result if result else 0
        except Exception as e:
            print(f"Error al obtener total de cuotas: {e}")
            return 0
    
    def obtener_deuda_total_creditos(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT meses_sin_intereses, meses_pagados, cuota_mensual FROM creditos WHERE pagado = 0")
            creditos = cursor.fetchall()
            total = sum((meses_totales - meses_pagados) * cuota for meses_totales, meses_pagados, cuota in creditos)
            return total
        except Exception as e:
            print(f"Error al obtener deuda total de créditos: {e}")
            return 0
    
    def registrar_pago_credito(self, id_credito):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT meses_sin_intereses, meses_pagados FROM creditos WHERE id = ?", (id_credito,))
            result = cursor.fetchone()
            if result:
                meses_totales, meses_pagados = result
                nuevos_meses_pagados = meses_pagados + 1
                
                # Si se pagaron todos los meses, marcar como pagado
                if nuevos_meses_pagados >= meses_totales:
                    cursor.execute("UPDATE creditos SET meses_pagados = ?, pagado = 1 WHERE id = ?", 
                                   (meses_totales, id_credito))
                else:
                    cursor.execute("UPDATE creditos SET meses_pagados = ? WHERE id = ?", 
                                   (nuevos_meses_pagados, id_credito))
                self.conn.commit()
                return True
        except Exception as e:
            print(f"Error al registrar pago de crédito: {e}")
            return False
    
    def borrar_credito(self, id_credito):
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE creditos SET pagado = 1 WHERE id = ?", (id_credito,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error al borrar crédito: {e}")
            return False
    
    # --- Métodos para Cuentas Bancarias ---
    
    def agregar_cuenta_bancaria(self, nombre_banco, tipo_cuenta, saldo_inicial=0, limite_credito=0):
        try:
            cursor = self.conn.cursor()
            fecha_creacion = datetime.datetime.now().strftime("%Y-%m-%d")
            cursor.execute("INSERT INTO cuentas_bancarias (nombre_banco, tipo_cuenta, saldo, limite_credito, fecha_creacion) VALUES (?, ?, ?, ?, ?)",
                           (nombre_banco, tipo_cuenta, saldo_inicial, limite_credito, fecha_creacion))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error al agregar cuenta bancaria: {e}")
            return False
    
    def obtener_cuentas_bancarias(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM cuentas_bancarias WHERE activa = 1 ORDER BY nombre_banco")
            return cursor.fetchall()
        except Exception as e:
            print(f"Error al obtener cuentas bancarias: {e}")
            return []
    
    def obtener_saldo_total_bancos(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT SUM(saldo) FROM cuentas_bancarias WHERE activa = 1")
            result = cursor.fetchone()[0]
            return result if result else 0
        except Exception as e:
            print(f"Error al obtener saldo total: {e}")
            return 0
    
    def actualizar_saldo_cuenta(self, id_cuenta, nuevo_saldo):
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE cuentas_bancarias SET saldo = ? WHERE id = ?", (nuevo_saldo, id_cuenta))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error al actualizar saldo: {e}")
            return False
    
    def agregar_monto_cuenta(self, id_cuenta, monto):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT saldo FROM cuentas_bancarias WHERE id = ?", (id_cuenta,))
            result = cursor.fetchone()
            if result:
                nuevo_saldo = result[0] + monto
                return self.actualizar_saldo_cuenta(id_cuenta, nuevo_saldo)
        except Exception as e:
            print(f"Error al agregar monto: {e}")
            return False
    
    def retirar_monto_cuenta(self, id_cuenta, monto):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT saldo FROM cuentas_bancarias WHERE id = ?", (id_cuenta,))
            result = cursor.fetchone()
            if result:
                nuevo_saldo = result[0] - monto
                return self.actualizar_saldo_cuenta(id_cuenta, nuevo_saldo)
        except Exception as e:
            print(f"Error al retirar monto: {e}")
            return False
    
    def borrar_cuenta_bancaria(self, id_cuenta):
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE cuentas_bancarias SET activa = 0 WHERE id = ?", (id_cuenta,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error al borrar cuenta: {e}")
            return False
    
    def close(self):
        """Cierra la conexión a la base de datos"""
        if self.conn:
            self.conn.close()

# --- Interfaz Gráfica (Flet) ---
def main(page: ft.Page):
    # Configuración para móvil
    page.title = "💰 Mis Finanzas"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.scroll = ft.ScrollMode.AUTO
    
    # Configuración óptima para móvil y PC
    try:
        # Solo ajustar tamaño en PC, en móvil se adapta automáticamente
        if not page.web:
            page.window_width = 400
            page.window_height = 800
    except:
        pass
    
    db = Database()
    
    # Estado para navegación
    vista_actual = "inicio"  # "inicio", "suscripciones", "prestamos", "creditos", "ahorros", "bancos", "balance" 

    # --- Componentes de UI ---
    
    # Texto del Balance
    txt_balance_total = ft.Text("$0", size=36, weight=ft.FontWeight.BOLD)
    txt_ingresos = ft.Text("$0", color="green", size=16, weight=ft.FontWeight.BOLD)
    txt_gastos = ft.Text("$0", color="red", size=16, weight=ft.FontWeight.BOLD)
    txt_suscripciones = ft.Text("$0", color="orange", size=16, weight=ft.FontWeight.BOLD)
    txt_prestamos = ft.Text("$0", color="purple", size=16, weight=ft.FontWeight.BOLD)
    txt_creditos = ft.Text("$0", color="indigo", size=16, weight=ft.FontWeight.BOLD)
    txt_ahorros = ft.Text("$0", color="teal", size=16, weight=ft.FontWeight.BOLD)
    txt_bancos = ft.Text("$0", color="cyan900", size=16, weight=ft.FontWeight.BOLD)
    txt_disponible = ft.Text("$0", size=20, weight=ft.FontWeight.BOLD, color="blue700")

    # Contenedores para diferentes vistas
    contenedor_principal = ft.Column(spacing=0, expand=True)

    # Campos para agregar nuevo movimiento
    input_desc = ft.TextField(
        label="Descripción",
        hint_text="Ej: Supermercado",
        color="black",
        text_size=16,
        border_color="blue700",
        focused_border_color="blue900"
    )
    input_monto = ft.TextField(
        label="Monto",
        keyboard_type=ft.KeyboardType.NUMBER,
        color="black",
        text_size=16,
        border_color="blue700",
        focused_border_color="blue900"
    )
    dropdown_tipo = ft.Dropdown(
        label="Tipo",
        options=[ft.dropdown.Option("gasto"), ft.dropdown.Option("ingreso")],
        value="gasto",
        on_change=lambda e: actualizar_opciones_destino()
    )
    dropdown_cat = ft.Dropdown(
        label="Categoría",
        options=[
            ft.dropdown.Option("Comida", "🍔 Comida"),
            ft.dropdown.Option("Transporte", "🚗 Transporte"),
            ft.dropdown.Option("Servicios", "💡 Servicios"),
            ft.dropdown.Option("Ocio", "🎮 Ocio"),
            ft.dropdown.Option("Salud", "💊 Salud"),
            ft.dropdown.Option("Salario", "💰 Salario"),
            ft.dropdown.Option("Compras", "🛒 Compras"),
            ft.dropdown.Option("Educación", "📚 Educación"),
            ft.dropdown.Option("Otro", "📌 Otro"),
        ],
        value="Comida"
    )
    dropdown_destino_movimiento = ft.Dropdown(
        label="Método de pago",
        options=[
            ft.dropdown.Option("efectivo", "💵 Efectivo"),
            ft.dropdown.Option("banco", "🏦 Banco")
        ],
        value="efectivo",
        visible=True,
        on_change=lambda e: actualizar_selector_banco()
    )
    dropdown_banco_movimiento = ft.Dropdown(
        label="Selecciona el banco",
        options=[],
        visible=False
    )
    
    def actualizar_opciones_destino():
        """Actualiza las etiquetas y opciones según el tipo de movimiento"""
        es_ingreso = dropdown_tipo.value == "ingreso"
        
        # Cambiar la etiqueta según el tipo
        if es_ingreso:
            dropdown_destino_movimiento.label = "Destino del ingreso"
        else:
            dropdown_destino_movimiento.label = "Método de pago"
        
        dropdown_banco_movimiento.visible = False
        
        # Obtener bancos disponibles
        cuentas = db.obtener_cuentas_bancarias()
        opciones = []
        for cuenta in cuentas:
            id_cuenta, nombre_banco, tipo_cuenta, saldo, limite_credito, fecha_creacion, activa = cuenta
            opciones.append(ft.dropdown.Option(f"banco_{id_cuenta}", f"{nombre_banco} ({tipo_cuenta})"))
        dropdown_banco_movimiento.options = opciones
        if opciones:
            dropdown_banco_movimiento.value = opciones[0].key
        
        page.update()
    
    def actualizar_selector_banco():
        """Muestra el selector de banco solo si se elige 'banco'"""
        dropdown_banco_movimiento.visible = dropdown_destino_movimiento.value == "banco"
        page.update()

    # --- Funciones de Lógica ---

    def actualizar_balance():
        """Actualiza los textos del balance"""
        ingresos, gastos, total = db.obtener_balance()
        total_suscripciones = db.obtener_total_suscripciones()
        total_cuotas_prestamos = db.obtener_total_cuotas_prestamos()
        total_cuotas_creditos = db.obtener_total_cuotas_creditos()
        total_ahorros = db.obtener_total_ahorros()
        total_bancos = db.obtener_saldo_total_bancos()
        disponible = total - total_suscripciones - total_cuotas_prestamos - total_cuotas_creditos
        
        txt_balance_total.value = f"${total:,.0f}"
        txt_ingresos.value = f"${ingresos:,.0f}"
        txt_gastos.value = f"${gastos:,.0f}"
        txt_suscripciones.value = f"${total_suscripciones:,.0f}"
        txt_prestamos.value = f"${total_cuotas_prestamos:,.0f}"
        txt_creditos.value = f"${total_cuotas_creditos:,.0f}"
        txt_ahorros.value = f"${total_ahorros:,.0f}"
        txt_bancos.value = f"${total_bancos:,.0f}"
        txt_disponible.value = f"${disponible:,.0f}"

    def crear_vista_inicio():
        """Crea la vista principal con movimientos"""
        lista_movimientos = ft.ListView(spacing=10, padding=10, expand=True)
        
        movimientos = db.obtener_movimientos()
        
        if not movimientos:
            lista_movimientos.controls.append(
                ft.Container(
                    content=ft.Text("No hay movimientos aún.\n¡Agrega tu primer movimiento!", 
                                   italic=True, text_align=ft.TextAlign.CENTER, size=14, color="grey"),
                    padding=40
                )
            )
        else:
            for mov in movimientos:
                # mov = (id, tipo, categoria, monto, desc, fecha) o (id, tipo, categoria, monto, desc, fecha, modo)
                if len(mov) == 7:  # BD antigua con columna 'modo'
                    id_mov, tipo, cat, monto, desc, fecha, modo = mov
                else:  # BD nueva sin columna 'modo'
                    id_mov, tipo, cat, monto, desc, fecha = mov
                
                icono = "trending_down" if tipo == "gasto" else "trending_up"
                color_icono = "red" if tipo == "gasto" else "green"
                bgcolor_card = "#fff5f5" if tipo == "gasto" else "#f0fff4"
                
                item = ft.Container(
                    content=ft.Row([
                        ft.Icon(icono, color=color_icono, size=28),
                        ft.Column([
                            ft.Text(desc, weight=ft.FontWeight.BOLD, size=15),
                            ft.Text(f"{cat} · {fecha}", size=12, color="grey600"),
                        ], expand=True, spacing=2),
                        ft.Column([
                            ft.Text(f"${monto:,.0f}", weight=ft.FontWeight.BOLD, color=color_icono, size=16),
                            ft.IconButton(
                                icon="delete_outline", 
                                icon_color="grey400",
                                icon_size=20,
                                tooltip="Borrar",
                                on_click=lambda e, x=id_mov: borrar_movimiento(x)
                            )
                        ], alignment=ft.MainAxisAlignment.END, horizontal_alignment=ft.CrossAxisAlignment.END)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=12,
                    border_radius=12,
                    bgcolor=bgcolor_card,
                    border=ft.border.all(1, "#e0e0e0"),
                    shadow=ft.BoxShadow(spread_radius=0, blur_radius=4, color="black12", offset=ft.Offset(0, 2))
                )
                lista_movimientos.controls.append(item)
        
        return ft.Column([
            crear_resumen_balance(),
            ft.Divider(height=1, color="grey300"),
            ft.Container(
                content=ft.Text("📋 Movimientos Recientes", size=16, weight=ft.FontWeight.BOLD),
                padding=ft.padding.only(left=15, top=10, bottom=5)
            ),
            lista_movimientos
        ], spacing=0, expand=True)
    
    def crear_vista_suscripciones():
        """Crea la vista de suscripciones"""
        lista_subs = ft.ListView(spacing=10, padding=10, expand=True)
        
        suscripciones = db.obtener_suscripciones()
        total = db.obtener_total_suscripciones()
        
        # Header con total
        header = ft.Container(
            content=ft.Column([
                ft.Text("📆 Suscripciones Activas", size=20, weight=ft.FontWeight.BOLD),
                ft.Divider(height=10, color="transparent"),
                ft.Row([
                    ft.Text("Total mensual:", size=16, color="grey700"),
                    ft.Text(f"${total:,.0f}", size=24, weight=ft.FontWeight.BOLD, color="orange")
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ]),
            padding=20,
            bgcolor="orange50",
            border_radius=15,
            margin=10
        )
        
        if not suscripciones:
            lista_subs.controls.append(
                ft.Container(
                    content=ft.Text("No tienes suscripciones activas.\n¡Agrega tus servicios recurrentes!", 
                                   italic=True, text_align=ft.TextAlign.CENTER, size=14, color="grey"),
                    padding=40
                )
            )
        else:
            for sub in suscripciones:
                # sub = (id, nombre, monto, dia_cobro, activa)
                id_sub, nombre, monto, dia_cobro, activa = sub
                
                item = ft.Container(
                    content=ft.Row([
                        ft.Icon("subscriptions", color="orange", size=28),
                        ft.Column([
                            ft.Text(nombre, weight=ft.FontWeight.BOLD, size=15),
                            ft.Text(f"Se cobra el día {dia_cobro} de cada mes", size=12, color="grey600"),
                        ], expand=True, spacing=2),
                        ft.Column([
                            ft.Text(f"${monto:,.0f}/mes", weight=ft.FontWeight.BOLD, color="orange", size=16),
                            ft.IconButton(
                                icon="delete_outline", 
                                icon_color="grey400",
                                icon_size=20,
                                tooltip="Eliminar",
                                on_click=lambda e, x=id_sub: borrar_suscripcion(x)
                            )
                        ], alignment=ft.MainAxisAlignment.END, horizontal_alignment=ft.CrossAxisAlignment.END)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=12,
                    border_radius=12,
                    bgcolor="white",
                    border=ft.border.all(1, "orange200"),
                    shadow=ft.BoxShadow(spread_radius=0, blur_radius=4, color="black12", offset=ft.Offset(0, 2))
                )
                lista_subs.controls.append(item)
        
        return ft.Column([header, lista_subs], spacing=0, expand=True)
    
    def crear_vista_prestamos():
        """Crea la vista de préstamos bancarios"""
        lista_prestamos = ft.ListView(spacing=10, padding=10, expand=True)
        
        prestamos = db.obtener_prestamos()
        total_cuotas = db.obtener_total_cuotas_prestamos()
        deuda_total = db.obtener_deuda_total()
        
        # Header con totales
        header = ft.Container(
            content=ft.Column([
                ft.Text("🏦 Préstamos Bancarios", size=20, weight=ft.FontWeight.BOLD),
                ft.Divider(height=10, color="transparent"),
                ft.Row([
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Cuotas/mes", size=12, color="grey700"),
                            ft.Text(f"${total_cuotas:,.0f}", size=20, weight=ft.FontWeight.BOLD, color="purple")
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        expand=True
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Deuda total", size=12, color="grey700"),
                            ft.Text(f"${deuda_total:,.0f}", size=20, weight=ft.FontWeight.BOLD, color="red")
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        expand=True
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_AROUND)
            ]),
            padding=20,
            bgcolor="purple50",
            border_radius=15,
            margin=10
        )
        
        if not prestamos:
            lista_prestamos.controls.append(
                ft.Container(
                    content=ft.Text("No tienes préstamos registrados.\n¡Mantén control de tus deudas bancarias!", 
                                   italic=True, text_align=ft.TextAlign.CENTER, size=14, color="grey"),
                    padding=40
                )
            )
        else:
            for prestamo in prestamos:
                # prestamo = (id, banco, monto_total, monto_pagado, cuota_mensual, dia_pago, fecha_inicio, activo)
                id_pres, banco, monto_total, monto_pagado, cuota_mensual, dia_pago, fecha_inicio, activo = prestamo
                
                saldo_pendiente = monto_total - monto_pagado
                porcentaje_pagado = (monto_pagado / monto_total * 100) if monto_total > 0 else 0
                
                item = ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon("account_balance", color="purple", size=28),
                            ft.Column([
                                ft.Text(banco, weight=ft.FontWeight.BOLD, size=15),
                                ft.Text(f"Cuota: ${cuota_mensual:,.0f}/mes · Día {dia_pago}", size=12, color="grey600"),
                            ], expand=True, spacing=2),
                            ft.IconButton(
                                icon="delete_outline", 
                                icon_color="grey400",
                                icon_size=20,
                                tooltip="Eliminar",
                                on_click=lambda e, x=id_pres: borrar_prestamo(x)
                            )
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Divider(height=5, color="transparent"),
                        ft.Row([
                            ft.Column([
                                ft.Text("Pagado", size=11, color="grey600"),
                                ft.Text(f"${monto_pagado:,.0f}", size=14, weight=ft.FontWeight.BOLD, color="green"),
                            ]),
                            ft.Column([
                                ft.Text("Pendiente", size=11, color="grey600"),
                                ft.Text(f"${saldo_pendiente:,.0f}", size=14, weight=ft.FontWeight.BOLD, color="red"),
                            ]),
                            ft.Column([
                                ft.Text("Total", size=11, color="grey600"),
                                ft.Text(f"${monto_total:,.0f}", size=14, weight=ft.FontWeight.BOLD),
                            ]),
                        ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                        ft.ProgressBar(value=porcentaje_pagado/100, color="purple", bgcolor="purple100"),
                        ft.Text(f"{porcentaje_pagado:.1f}% pagado", size=11, color="purple", text_align=ft.TextAlign.CENTER),
                        ft.ElevatedButton(
                            "Registrar Pago",
                            icon="payment",
                            on_click=lambda e, x=id_pres: abrir_registrar_pago(x),
                            bgcolor="purple700",
                            color="white",
                            width=float("inf")
                        )
                    ], spacing=8),
                    padding=12,
                    border_radius=12,
                    bgcolor="white",
                    border=ft.border.all(1, "purple200"),
                    shadow=ft.BoxShadow(spread_radius=0, blur_radius=4, color="black12", offset=ft.Offset(0, 2))
                )
                lista_prestamos.controls.append(item)
        
        return ft.Column([header, lista_prestamos], spacing=0, expand=True)
    
    def crear_vista_creditos():
        """Crea la vista de compras a crédito"""
        lista_creditos = ft.ListView(spacing=10, padding=10, expand=True)
        
        creditos = db.obtener_creditos()
        total_cuotas = db.obtener_total_cuotas_creditos()
        deuda_total = db.obtener_deuda_total_creditos()
        
        # Header con totales
        header = ft.Container(
            content=ft.Column([
                ft.Text("💳 Compras a Crédito", size=20, weight=ft.FontWeight.BOLD),
                ft.Divider(height=10, color="transparent"),
                ft.Row([
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Cuotas/mes", size=12, color="grey700"),
                            ft.Text(f"${total_cuotas:,.0f}", size=20, weight=ft.FontWeight.BOLD, color="indigo")
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        expand=True
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Deuda total", size=12, color="grey700"),
                            ft.Text(f"${deuda_total:,.0f}", size=20, weight=ft.FontWeight.BOLD, color="red")
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        expand=True
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_AROUND)
            ]),
            padding=20,
            bgcolor="indigo50",
            border_radius=15,
            margin=10
        )
        
        if not creditos:
            lista_creditos.controls.append(
                ft.Container(
                    content=ft.Text("No tienes compras a crédito.\n¡Controla tus compras en meses sin intereses!", 
                                   italic=True, text_align=ft.TextAlign.CENTER, size=14, color="grey"),
                    padding=40
                )
            )
        else:
            for credito in creditos:
                # credito = (id, descripcion, banco, monto_total, meses_sin_intereses, cuota_mensual, meses_pagados, fecha_compra, tasa_interes, pagado)
                id_cred, descripcion, banco, monto_total, meses_totales, cuota_mensual, meses_pagados, fecha_compra, tasa_interes, pagado = credito
                
                meses_restantes = meses_totales - meses_pagados
                saldo_pendiente = meses_restantes * cuota_mensual
                porcentaje_pagado = (meses_pagados / meses_totales * 100) if meses_totales > 0 else 0
                
                # Determinar si tiene intereses
                tipo_credito = "Sin intereses" if tasa_interes == 0 else f"Interés: {tasa_interes:.1f}% mensual"
                
                item = ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon("credit_card", color="indigo", size=28),
                            ft.Column([
                                ft.Text(descripcion, weight=ft.FontWeight.BOLD, size=15),
                                ft.Text(f"{banco} · {fecha_compra}", size=12, color="grey600"),
                                ft.Text(tipo_credito, size=11, color="indigo", italic=True),
                            ], expand=True, spacing=2),
                            ft.IconButton(
                                icon="delete_outline", 
                                icon_color="grey400",
                                icon_size=20,
                                tooltip="Eliminar",
                                on_click=lambda e, x=id_cred: borrar_credito(x)
                            )
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Divider(height=5, color="transparent"),
                        ft.Row([
                            ft.Column([
                                ft.Text("Cuota mensual", size=11, color="grey600"),
                                ft.Text(f"${cuota_mensual:,.0f}", size=14, weight=ft.FontWeight.BOLD, color="indigo"),
                            ]),
                            ft.Column([
                                ft.Text("Meses", size=11, color="grey600"),
                                ft.Text(f"{meses_pagados}/{meses_totales}", size=14, weight=ft.FontWeight.BOLD),
                            ]),
                            ft.Column([
                                ft.Text("Pendiente", size=11, color="grey600"),
                                ft.Text(f"${saldo_pendiente:,.0f}", size=14, weight=ft.FontWeight.BOLD, color="red"),
                            ]),
                        ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                        ft.ProgressBar(value=porcentaje_pagado/100, color="indigo", bgcolor="indigo100"),
                        ft.Text(f"{porcentaje_pagado:.1f}% pagado · Faltan {meses_restantes} meses", size=11, color="indigo", text_align=ft.TextAlign.CENTER),
                        ft.ElevatedButton(
                            "Pagar Mensualidad",
                            icon="payment",
                            on_click=lambda e, x=id_cred: registrar_pago_credito_directo(x),
                            bgcolor="indigo700",
                            color="white",
                            width=float("inf")
                        )
                    ], spacing=8),
                    padding=12,
                    border_radius=12,
                    bgcolor="white",
                    border=ft.border.all(1, "indigo200"),
                    shadow=ft.BoxShadow(spread_radius=0, blur_radius=4, color="black12", offset=ft.Offset(0, 2))
                )
                lista_creditos.controls.append(item)
        
        return ft.Column([header, lista_creditos], spacing=0, expand=True)
    
    def crear_vista_ahorros():
        """Crea la vista de ahorros"""
        lista_ahorros = ft.ListView(spacing=10, padding=10, expand=True)
        
        ahorros = db.obtener_ahorros()
        total_ahorrado = db.obtener_total_ahorros()
        
        # Header con total
        header = ft.Container(
            content=ft.Column([
                ft.Text("🎯 Mis Ahorros", size=20, weight=ft.FontWeight.BOLD),
                ft.Divider(height=10, color="transparent"),
                ft.Row([
                    ft.Text("Total ahorrado:", size=16, color="grey700"),
                    ft.Text(f"${total_ahorrado:,.0f}", size=24, weight=ft.FontWeight.BOLD, color="teal")
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ]),
            padding=20,
            bgcolor="teal50",
            border_radius=15,
            margin=10
        )
        
        if not ahorros:
            lista_ahorros.controls.append(
                ft.Container(
                    content=ft.Text("No tienes metas de ahorro activas.\n¡Empieza a ahorrar para tus objetivos!", 
                                   italic=True, text_align=ft.TextAlign.CENTER, size=14, color="grey"),
                    padding=40
                )
            )
        else:
            for ahorro in ahorros:
                # ahorro = (id, nombre, meta, monto_actual, fecha_inicio, completado)
                id_aho, nombre, meta, monto_actual, fecha_inicio, completado = ahorro
                
                falta = meta - monto_actual
                porcentaje = (monto_actual / meta * 100) if meta > 0 else 0
                
                item = ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon("savings", color="teal", size=28),
                            ft.Column([
                                ft.Text(nombre, weight=ft.FontWeight.BOLD, size=15),
                                ft.Text(f"Desde {fecha_inicio}", size=12, color="grey600"),
                            ], expand=True, spacing=2),
                            ft.IconButton(
                                icon="delete_outline", 
                                icon_color="grey400",
                                icon_size=20,
                                tooltip="Eliminar",
                                on_click=lambda e, x=id_aho: borrar_ahorro(x)
                            )
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Divider(height=5, color="transparent"),
                        ft.Row([
                            ft.Column([
                                ft.Text("Ahorrado", size=11, color="grey600"),
                                ft.Text(f"${monto_actual:,.0f}", size=14, weight=ft.FontWeight.BOLD, color="teal"),
                            ]),
                            ft.Column([
                                ft.Text("Falta", size=11, color="grey600"),
                                ft.Text(f"${falta:,.0f}", size=14, weight=ft.FontWeight.BOLD, color="orange"),
                            ]),
                            ft.Column([
                                ft.Text("Meta", size=11, color="grey600"),
                                ft.Text(f"${meta:,.0f}", size=14, weight=ft.FontWeight.BOLD),
                            ]),
                        ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                        ft.ProgressBar(value=porcentaje/100, color="teal", bgcolor="teal100"),
                        ft.Text(f"{porcentaje:.1f}% completado", size=11, color="teal", text_align=ft.TextAlign.CENTER),
                        ft.Row([
                            ft.ElevatedButton(
                                "Agregar",
                                icon="add",
                                on_click=lambda e, x=id_aho: abrir_agregar_monto(x),
                                bgcolor="teal700",
                                color="white",
                                expand=True
                            ),
                            ft.ElevatedButton(
                                "Retirar",
                                icon="remove",
                                on_click=lambda e, x=id_aho: abrir_retirar_monto(x),
                                bgcolor="red700",
                                color="white",
                                expand=True
                            ),
                        ], spacing=10)
                    ], spacing=8),
                    padding=12,
                    border_radius=12,
                    bgcolor="white",
                    border=ft.border.all(1, "teal200"),
                    shadow=ft.BoxShadow(spread_radius=0, blur_radius=4, color="black12", offset=ft.Offset(0, 2))
                )
                lista_ahorros.controls.append(item)
        
        return ft.Column([header, lista_ahorros], spacing=0, expand=True)
    
    def crear_vista_bancos():
        """Crea la vista de cuentas bancarias"""
        lista_bancos = ft.ListView(spacing=10, padding=10, expand=True)
        
        cuentas = db.obtener_cuentas_bancarias()
        total_saldo = db.obtener_saldo_total_bancos()
        
        # Header con total
        header = ft.Container(
            content=ft.Column([
                ft.Text("🏦 Mis Cuentas Bancarias", size=20, weight=ft.FontWeight.BOLD),
                ft.Divider(height=10, color="transparent"),
                ft.Row([
                    ft.Text("Saldo total:", size=16, color="grey700"),
                    ft.Text(f"${total_saldo:,.0f}", size=24, weight=ft.FontWeight.BOLD, color="cyan900")
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ]),
            padding=20,
            bgcolor="cyan50",
            border_radius=15,
            margin=10
        )
        
        if not cuentas:
            lista_bancos.controls.append(
                ft.Container(
                    content=ft.Text("No tienes cuentas registradas.\n¡Agrega tus cuentas bancarias!", 
                                   italic=True, text_align=ft.TextAlign.CENTER, size=14, color="grey"),
                    padding=40
                )
            )
        else:
            for cuenta in cuentas:
                # cuenta = (id, nombre_banco, tipo_cuenta, saldo, limite_credito, fecha_creacion, activa)
                id_cuenta, nombre_banco, tipo_cuenta, saldo, limite_credito, fecha_creacion, activa = cuenta
                
                # Iconos y colores según tipo de cuenta
                iconos = {
                    "debito": ("payment", "blue"),
                    "credito": ("credit_card", "orange"),
                    "ahorro": ("savings", "green"),
                    "inversion": ("trending_up", "purple")
                }
                icono, color = iconos.get(tipo_cuenta, ("account_balance", "cyan"))
                
                # Mostrar información adicional para tarjetas de crédito
                info_adicional = ""
                if tipo_cuenta == "credito" and limite_credito > 0:
                    disponible_credito = limite_credito - abs(saldo)
                    info_adicional = f"Disponible: ${disponible_credito:,.0f} de ${limite_credito:,.0f}"
                
                item = ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(icono, color=color, size=28),
                            ft.Column([
                                ft.Text(nombre_banco, weight=ft.FontWeight.BOLD, size=15),
                                ft.Text(f"{tipo_cuenta.capitalize()} · {fecha_creacion}", size=12, color="grey600"),
                            ], expand=True, spacing=2),
                            ft.IconButton(
                                icon="delete_outline", 
                                icon_color="grey400",
                                icon_size=20,
                                tooltip="Eliminar",
                                on_click=lambda e, x=id_cuenta: borrar_cuenta_bancaria(x)
                            )
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Divider(height=5, color="transparent"),
                        ft.Container(
                            content=ft.Column([
                                ft.Text("Saldo actual", size=12, color="grey600"),
                                ft.Text(f"${saldo:,.0f}", size=24, weight=ft.FontWeight.BOLD, color="cyan900"),
                                ft.Text(info_adicional, size=11, color="grey600") if info_adicional else ft.Container(),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            padding=10,
                            bgcolor="cyan50",
                            border_radius=8,
                        ),
                        ft.Divider(height=5, color="transparent"),
                        ft.Row([
                            ft.ElevatedButton(
                                "Depositar",
                                icon="add",
                                on_click=lambda e, x=id_cuenta: abrir_depositar_banco(x),
                                bgcolor="green700",
                                color="white",
                                expand=True
                            ),
                            ft.ElevatedButton(
                                "Retirar",
                                icon="remove",
                                on_click=lambda e, x=id_cuenta: abrir_retirar_banco(x),
                                bgcolor="red700",
                                color="white",
                                expand=True
                            ),
                        ], spacing=10)
                    ], spacing=8),
                    padding=12,
                    border_radius=12,
                    bgcolor="white",
                    border=ft.border.all(1, "cyan200"),
                    shadow=ft.BoxShadow(spread_radius=0, blur_radius=4, color="black12", offset=ft.Offset(0, 2))
                )
                lista_bancos.controls.append(item)
        
        return ft.Column([header, lista_bancos], spacing=0, expand=True)
    
    def exportar_movimientos_a_excel(mes, anio):
        """Exporta los movimientos mensuales a un archivo Excel"""
        try:
            # Obtener datos
            movimientos = db.obtener_movimientos_mensuales(mes, anio)
            ingresos_mes, gastos_mes = db.obtener_balance_mensual(mes, anio)
            total_subs = db.obtener_total_suscripciones()
            total_cuotas = db.obtener_total_cuotas_prestamos()
            total_cuotas_creditos = db.obtener_total_cuotas_creditos()
            balance_mes = ingresos_mes - gastos_mes
            
            meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            mes_nombre = meses[mes - 1]
            
            # Crear libro de Excel
            wb = Workbook()
            ws = wb.active
            ws.title = f"{mes_nombre} {anio}"
            
            # Estilos
            header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF", size=12)
            title_font = Font(bold=True, size=14)
            
            # Título
            ws.merge_cells('A1:E1')
            ws['A1'] = f"Reporte de Movimientos - {mes_nombre} {anio}"
            ws['A1'].font = title_font
            ws['A1'].alignment = Alignment(horizontal='center')
            
            # Resumen
            ws['A3'] = "RESUMEN DEL MES"
            ws['A3'].font = Font(bold=True, size=12)
            
            ws['A4'] = "Total Ingresos:"
            ws['B4'] = f"${ingresos_mes:,.2f}"
            ws['B4'].font = Font(color="008000", bold=True)
            
            ws['A5'] = "Total Gastos:"
            ws['B5'] = f"${gastos_mes:,.2f}"
            ws['B5'].font = Font(color="FF0000", bold=True)
            
            ws['A6'] = "Suscripciones:"
            ws['B6'] = f"${total_subs:,.2f}"
            
            ws['A7'] = "Cuotas Préstamos:"
            ws['B7'] = f"${total_cuotas:,.2f}"
            
            ws['A8'] = "Cuotas Créditos:"
            ws['B8'] = f"${total_cuotas_creditos:,.2f}"
            
            ws['A9'] = "Balance Final:"
            ws['B9'] = f"${balance_mes:,.2f}"
            ws['B9'].font = Font(bold=True, size=12)
            
            # Encabezados de movimientos
            ws['A11'] = "Fecha"
            ws['B11'] = "Tipo"
            ws['C11'] = "Categoría"
            ws['D11'] = "Descripción"
            ws['E11'] = "Monto"
            
            for cell in ['A11', 'B11', 'C11', 'D11', 'E11']:
                ws[cell].fill = header_fill
                ws[cell].font = header_font
                ws[cell].alignment = Alignment(horizontal='center')
            
            # Datos de movimientos
            fila = 12
            for mov in movimientos:
                id_mov, tipo, categoria, monto, descripcion, fecha = mov
                
                ws[f'A{fila}'] = fecha
                ws[f'B{fila}'] = tipo.upper()
                ws[f'C{fila}'] = categoria
                ws[f'D{fila}'] = descripcion
                ws[f'E{fila}'] = f"${monto:,.2f}"
                
                # Colorear según tipo
                if tipo == 'ingreso':
                    ws[f'B{fila}'].font = Font(color="008000")
                    ws[f'E{fila}'].font = Font(color="008000")
                else:
                    ws[f'B{fila}'].font = Font(color="FF0000")
                    ws[f'E{fila}'].font = Font(color="FF0000")
                
                fila += 1
            
            # Ajustar anchos de columna
            ws.column_dimensions['A'].width = 20
            ws.column_dimensions['B'].width = 12
            ws.column_dimensions['C'].width = 15
            ws.column_dimensions['D'].width = 30
            ws.column_dimensions['E'].width = 15
            
            # Guardar archivo
            nombre_archivo = f"Movimientos_{mes_nombre}_{anio}.xlsx"
            ruta_documentos = os.path.join(os.path.expanduser('~'), 'Documents')
            ruta_completa = os.path.join(ruta_documentos, nombre_archivo)
            
            wb.save(ruta_completa)
            return True, ruta_completa
            
        except Exception as e:
            print(f"Error al exportar a Excel: {e}")
            return False, str(e)
    
    def crear_vista_balance_mensual():
        """Crea la vista de balance mensual"""
        ahora = datetime.datetime.now()
        mes_actual = ahora.month
        anio_actual = ahora.year
        
        ingresos_mes, gastos_mes = db.obtener_balance_mensual(mes_actual, anio_actual)
        total_subs = db.obtener_total_suscripciones()
        total_cuotas = db.obtener_total_cuotas_prestamos()
        balance_mes = ingresos_mes - gastos_mes - total_subs - total_cuotas
        
        meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        mes_nombre = meses[mes_actual - 1]
        
        def exportar_excel(e):
            exito, mensaje = exportar_movimientos_a_excel(mes_actual, anio_actual)
            if exito:
                page.show_snack_bar(
                    ft.SnackBar(
                        content=ft.Text(f"✅ Excel exportado: {mensaje}"),
                        bgcolor="green",
                        duration=5000
                    )
                )
            else:
                page.show_snack_bar(
                    ft.SnackBar(
                        content=ft.Text(f"❌ Error: {mensaje}"),
                        bgcolor="red",
                        duration=5000
                    )
                )
        
        return ft.Column([
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(f"📊 Balance de {mes_nombre} {anio_actual}", size=20, weight=ft.FontWeight.BOLD, expand=True),
                        ft.IconButton(
                            icon="download",
                            icon_color="green",
                            tooltip="Exportar a Excel",
                            on_click=exportar_excel,
                            icon_size=28
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Divider(height=20, color="transparent"),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Ingresos del mes", size=14, color="grey700"),
                            ft.Text(f"${ingresos_mes:,.0f}", size=28, weight=ft.FontWeight.BOLD, color="green"),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=15,
                        bgcolor="green50",
                        border_radius=10,
                    ),
                    ft.Divider(height=10, color="transparent"),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Gastos del mes", size=14, color="grey700"),
                            ft.Text(f"${gastos_mes:,.0f}", size=28, weight=ft.FontWeight.BOLD, color="red"),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=15,
                        bgcolor="red50",
                        border_radius=10,
                    ),
                    ft.Divider(height=10, color="transparent"),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Suscripciones mensuales", size=14, color="grey700"),
                            ft.Text(f"${total_subs:,.0f}", size=28, weight=ft.FontWeight.BOLD, color="orange"),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=15,
                        bgcolor="orange50",
                        border_radius=10,
                    ),
                    ft.Divider(height=10, color="transparent"),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Cuotas de préstamos", size=14, color="grey700"),
                            ft.Text(f"${total_cuotas:,.0f}", size=28, weight=ft.FontWeight.BOLD, color="purple"),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=15,
                        bgcolor="purple50",
                        border_radius=10,
                    ),
                    ft.Divider(height=20, color="transparent"),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Balance Final", size=16, color="grey700", weight=ft.FontWeight.BOLD),
                            ft.Text(f"${balance_mes:,.0f}", size=36, weight=ft.FontWeight.BOLD, 
                                   color="green" if balance_mes >= 0 else "red"),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=20,
                        bgcolor="blue50",
                        border_radius=15,
                        border=ft.border.all(2, "blue700"),
                    ),
                ]),
                padding=20,
                expand=True
            )
        ], spacing=0, expand=True, scroll=ft.ScrollMode.AUTO)
    
    def crear_resumen_balance():
        """Crea el widget de resumen de balance"""
        return ft.Container(
            content=ft.Column([
                ft.Text("Balance Total", size=14, color="grey700", weight=ft.FontWeight.W_500),
                txt_balance_total,
                ft.Divider(height=5, color="transparent"),
                ft.Row([
                    ft.Container(
                        content=ft.Column([
                            ft.Icon("arrow_upward", color="green", size=18),
                            ft.Text("Ingresos", size=11, color="grey600"),
                            txt_ingresos
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                        padding=8,
                        bgcolor="green50",
                        border_radius=8,
                        expand=True
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Icon("arrow_downward", color="red", size=18),
                            ft.Text("Gastos", size=11, color="grey600"),
                            txt_gastos
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                        padding=8,
                        bgcolor="red50",
                        border_radius=8,
                        expand=True
                    ),
                ], spacing=8),
                ft.Divider(height=5, color="transparent"),
                ft.Row([
                    ft.Container(
                        content=ft.Column([
                            ft.Icon("subscriptions", color="orange", size=18),
                            ft.Text("Suscripciones", size=11, color="grey600"),
                            txt_suscripciones
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                        padding=8,
                        bgcolor="orange50",
                        border_radius=8,
                        expand=True
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Icon("account_balance", color="purple", size=18),
                            ft.Text("Préstamos", size=11, color="grey600"),
                            txt_prestamos
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                        padding=8,
                        bgcolor="purple50",
                        border_radius=8,
                        expand=True
                    ),
                ], spacing=8),
                ft.Divider(height=5, color="transparent"),
                ft.Row([
                    ft.Container(
                        content=ft.Column([
                            ft.Icon("credit_card", color="indigo", size=18),
                            ft.Text("Créditos", size=11, color="grey600"),
                            txt_creditos
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                        padding=8,
                        bgcolor="indigo50",
                        border_radius=8,
                        expand=True
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Icon("savings", color="teal", size=18),
                            ft.Text("Ahorros", size=11, color="grey600"),
                            txt_ahorros
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                        padding=8,
                        bgcolor="teal50",
                        border_radius=8,
                        expand=True
                    ),
                ], spacing=8),
                ft.Divider(height=5, color="transparent"),
                ft.Row([
                    ft.Container(
                        content=ft.Column([
                            ft.Icon("account_balance", color="cyan900", size=18),
                            ft.Text("En Bancos", size=11, color="grey600"),
                            txt_bancos
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                        padding=8,
                        bgcolor="cyan50",
                        border_radius=8,
                        expand=True
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Icon("account_balance_wallet", color="blue700", size=18),
                            ft.Text("Disponible", size=11, color="grey600"),
                            txt_disponible
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                        padding=8,
                        bgcolor="blue50",
                        border_radius=8,
                        expand=True
                    ),
                ], spacing=8),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
            padding=15,
            margin=10,
            bgcolor="white",
            border_radius=15,
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=8, color="black12", offset=ft.Offset(0, 2))
        )
    
    def actualizar_vista():
        """Actualiza la vista actual"""
        nonlocal vista_actual
        
        actualizar_balance()
        contenedor_principal.controls.clear()
        
        if vista_actual == "inicio":
            contenedor_principal.controls.append(crear_vista_inicio())
        elif vista_actual == "suscripciones":
            contenedor_principal.controls.append(crear_vista_suscripciones())
        elif vista_actual == "prestamos":
            contenedor_principal.controls.append(crear_vista_prestamos())
        elif vista_actual == "creditos":
            contenedor_principal.controls.append(crear_vista_creditos())
        elif vista_actual == "ahorros":
            contenedor_principal.controls.append(crear_vista_ahorros())
        elif vista_actual == "bancos":
            contenedor_principal.controls.append(crear_vista_bancos())
        elif vista_actual == "balance":
            contenedor_principal.controls.append(crear_vista_balance_mensual())
        
        page.update()

    def guardar_movimiento(e):
        # Limpiar errores previos
        input_desc.error_text = None
        input_monto.error_text = None
        
        # Validar campos vacíos
        if not input_desc.value or not input_monto.value:
            input_desc.error_text = "Requerido" if not input_desc.value else None
            input_monto.error_text = "Requerido" if not input_monto.value else None
            page.update()
            return
        
        # Validar formato de número
        try:
            monto = float(input_monto.value)
        except ValueError:
            input_monto.error_text = "Debe ser un número válido"
            page.update()
            return
        
        # Validar monto positivo
        if monto <= 0:
            input_monto.error_text = "Debe ser mayor a 0"
            page.update()
            return

        # Intentar guardar en BD
        if db.agregar_movimiento(
            dropdown_tipo.value,
            dropdown_cat.value,
            monto,
            input_desc.value
        ):
            # Si usa banco, agregar o retirar el monto de la cuenta
            if dropdown_destino_movimiento.value == "banco" and dropdown_banco_movimiento.value:
                # Extraer el ID del banco del valor seleccionado
                id_cuenta = int(dropdown_banco_movimiento.value.split("_")[1])
                
                if dropdown_tipo.value == "ingreso":
                    # Agregar monto al banco
                    db.agregar_monto_cuenta(id_cuenta, monto)
                else:
                    # Retirar monto del banco (gasto)
                    db.retirar_monto_cuenta(id_cuenta, monto)
            
            # Limpiar campos y cerrar diálogo
            input_desc.value = ""
            input_monto.value = ""
            input_desc.error_text = None
            input_monto.error_text = None
            dropdown_banco_movimiento.visible = False
            bottom_sheet_movimiento.open = False
            actualizar_vista()
        else:
            # Mostrar error si falla el guardado
            input_desc.error_text = "Error al guardar. Intenta de nuevo."
            page.update()
    
    def guardar_suscripcion(e):
        input_sub_nombre.error_text = None
        input_sub_monto.error_text = None
        input_sub_dia.error_text = None
        
        if not input_sub_nombre.value or not input_sub_monto.value or not input_sub_dia.value:
            input_sub_nombre.error_text = "Requerido" if not input_sub_nombre.value else None
            input_sub_monto.error_text = "Requerido" if not input_sub_monto.value else None
            input_sub_dia.error_text = "Requerido" if not input_sub_dia.value else None
            page.update()
            return
        
        try:
            monto = float(input_sub_monto.value)
            dia = int(input_sub_dia.value)
        except ValueError:
            input_sub_monto.error_text = "Debe ser un número"
            page.update()
            return
        
        if monto <= 0:
            input_sub_monto.error_text = "Debe ser mayor a 0"
            page.update()
            return
        
        if dia < 1 or dia > 31:
            input_sub_dia.error_text = "Debe estar entre 1 y 31"
            page.update()
            return
        
        if db.agregar_suscripcion(input_sub_nombre.value, monto, dia):
            input_sub_nombre.value = ""
            input_sub_monto.value = ""
            input_sub_dia.value = ""
            bottom_sheet_suscripcion.open = False
            actualizar_vista()
        else:
            input_sub_nombre.error_text = "Error al guardar"
            page.update()
    
    def guardar_prestamo(e):
        input_prest_banco.error_text = None
        input_prest_monto_total.error_text = None
        input_prest_cuota.error_text = None
        input_prest_dia.error_text = None
        
        if not input_prest_banco.value or not input_prest_monto_total.value or not input_prest_cuota.value or not input_prest_dia.value:
            input_prest_banco.error_text = "Requerido" if not input_prest_banco.value else None
            input_prest_monto_total.error_text = "Requerido" if not input_prest_monto_total.value else None
            input_prest_cuota.error_text = "Requerido" if not input_prest_cuota.value else None
            input_prest_dia.error_text = "Requerido" if not input_prest_dia.value else None
            page.update()
            return
        
        try:
            monto_total = float(input_prest_monto_total.value)
            cuota = float(input_prest_cuota.value)
            dia = int(input_prest_dia.value)
        except ValueError:
            input_prest_monto_total.error_text = "Debe ser un número"
            page.update()
            return
        
        if monto_total <= 0 or cuota <= 0:
            input_prest_monto_total.error_text = "Debe ser mayor a 0"
            input_prest_cuota.error_text = "Debe ser mayor a 0"
            page.update()
            return
        
        if dia < 1 or dia > 31:
            input_prest_dia.error_text = "Debe estar entre 1 y 31"
            page.update()
            return
        
        if db.agregar_prestamo(input_prest_banco.value, monto_total, cuota, dia):
            input_prest_banco.value = ""
            input_prest_monto_total.value = ""
            input_prest_cuota.value = ""
            input_prest_dia.value = ""
            bottom_sheet_prestamo.open = False
            actualizar_vista()
        else:
            input_prest_banco.error_text = "Error al guardar"
            page.update()
    
    def guardar_credito(e):
        input_credito_desc.error_text = None
        input_credito_banco.error_text = None
        input_credito_monto.error_text = None
        input_credito_meses.error_text = None
        input_credito_interes.error_text = None
        
        if not input_credito_desc.value or not input_credito_banco.value or not input_credito_monto.value or not input_credito_meses.value:
            input_credito_desc.error_text = "Requerido" if not input_credito_desc.value else None
            input_credito_banco.error_text = "Requerido" if not input_credito_banco.value else None
            input_credito_monto.error_text = "Requerido" if not input_credito_monto.value else None
            input_credito_meses.error_text = "Requerido" if not input_credito_meses.value else None
            page.update()
            return
        
        try:
            monto = float(input_credito_monto.value)
            meses = int(input_credito_meses.value)
            tasa_interes = float(input_credito_interes.value) if input_credito_interes.value else 0
        except ValueError:
            input_credito_monto.error_text = "Debe ser un número"
            page.update()
            return
        
        if monto <= 0 or meses <= 0:
            input_credito_monto.error_text = "Debe ser mayor a 0" if monto <= 0 else None
            input_credito_meses.error_text = "Debe ser mayor a 0" if meses <= 0 else None
            page.update()
            return
        
        if tasa_interes < 0:
            input_credito_interes.error_text = "No puede ser negativo"
            page.update()
            return
        
        if db.agregar_credito(input_credito_desc.value, input_credito_banco.value, monto, meses, tasa_interes):
            input_credito_desc.value = ""
            input_credito_banco.value = ""
            input_credito_monto.value = ""
            input_credito_meses.value = ""
            input_credito_interes.value = "0"
            bottom_sheet_credito.open = False
            actualizar_vista()
        else:
            input_credito_desc.error_text = "Error al guardar"
            page.update()
    
    def guardar_ahorro(e):
        input_ahorro_nombre.error_text = None
        input_ahorro_meta.error_text = None
        
        if not input_ahorro_nombre.value or not input_ahorro_meta.value:
            input_ahorro_nombre.error_text = "Requerido" if not input_ahorro_nombre.value else None
            input_ahorro_meta.error_text = "Requerido" if not input_ahorro_meta.value else None
            page.update()
            return
        
        try:
            meta = float(input_ahorro_meta.value)
        except ValueError:
            input_ahorro_meta.error_text = "Debe ser un número"
            page.update()
            return
        
        if meta <= 0:
            input_ahorro_meta.error_text = "Debe ser mayor a 0"
            page.update()
            return
        
        if db.agregar_ahorro(input_ahorro_nombre.value, meta):
            input_ahorro_nombre.value = ""
            input_ahorro_meta.value = ""
            bottom_sheet_ahorro.open = False
            actualizar_vista()
        else:
            input_ahorro_nombre.error_text = "Error al guardar"
            page.update()
    
    def guardar_cuenta_bancaria(e):
        input_banco_nombre.error_text = None
        input_banco_saldo.error_text = None
        input_banco_limite.error_text = None
        
        if not input_banco_nombre.value:
            input_banco_nombre.error_text = "Requerido"
            page.update()
            return
        
        try:
            saldo = float(input_banco_saldo.value) if input_banco_saldo.value else 0
            limite = float(input_banco_limite.value) if input_banco_limite.value else 0
        except ValueError:
            input_banco_saldo.error_text = "Debe ser un número"
            page.update()
            return
        
        if db.agregar_cuenta_bancaria(input_banco_nombre.value, dropdown_tipo_cuenta.value, saldo, limite):
            input_banco_nombre.value = ""
            input_banco_saldo.value = "0"
            input_banco_limite.value = "0"
            dropdown_tipo_cuenta.value = "debito"
            bottom_sheet_banco.open = False
            actualizar_vista()
        else:
            input_banco_nombre.error_text = "Error al guardar"
            page.update()

    def borrar_movimiento(id_mov):
        if db.borrar_movimiento(id_mov):
            actualizar_vista()
    
    def borrar_suscripcion(id_sub):
        if db.borrar_suscripcion(id_sub):
            actualizar_vista()
    
    def borrar_prestamo(id_pres):
        if db.borrar_prestamo(id_pres):
            actualizar_vista()
    
    def borrar_ahorro(id_aho):
        if db.borrar_ahorro(id_aho):
            actualizar_vista()
    
    def borrar_credito(id_cred):
        if db.borrar_credito(id_cred):
            actualizar_vista()
    
    def registrar_pago_credito_directo(id_cred):
        if db.registrar_pago_credito(id_cred):
            actualizar_vista()
    
    def borrar_cuenta_bancaria(id_cuenta):
        if db.borrar_cuenta_bancaria(id_cuenta):
            actualizar_vista()

    def cambiar_vista(e):
        nonlocal vista_actual
        vista_actual = ["inicio", "suscripciones", "prestamos", "creditos", "ahorros", "bancos", "balance"][e.control.selected_index]
        actualizar_vista()

    # --- Elementos de Navegación y Estructura ---
    
    # Campos para suscripciones
    input_sub_nombre = ft.TextField(
        label="Nombre",
        hint_text="Ej: Netflix, Spotify...",
        color="black",
        text_size=16,
        border_color="orange700",
        focused_border_color="orange900"
    )
    input_sub_monto = ft.TextField(
        label="Monto mensual",
        keyboard_type=ft.KeyboardType.NUMBER,
        color="black",
        text_size=16,
        border_color="orange700",
        focused_border_color="orange900"
    )
    input_sub_dia = ft.TextField(
        label="Día de cobro (1-31)",
        keyboard_type=ft.KeyboardType.NUMBER,
        color="black",
        text_size=16,
        border_color="orange700",
        focused_border_color="orange900"
    )
    
    # Campos para préstamos
    input_prest_banco = ft.TextField(
        label="Banco",
        hint_text="Ej: Banco Nacional, BBVA...",
        color="black",
        text_size=16,
        border_color="purple700",
        focused_border_color="purple900"
    )
    input_prest_monto_total = ft.TextField(
        label="Monto total del préstamo",
        keyboard_type=ft.KeyboardType.NUMBER,
        color="black",
        text_size=16,
        border_color="purple700",
        focused_border_color="purple900"
    )
    input_prest_cuota = ft.TextField(
        label="Cuota mensual",
        keyboard_type=ft.KeyboardType.NUMBER,
        color="black",
        text_size=16,
        border_color="purple700",
        focused_border_color="purple900"
    )
    input_prest_dia = ft.TextField(
        label="Día de pago (1-31)",
        keyboard_type=ft.KeyboardType.NUMBER,
        color="black",
        text_size=16,
        border_color="purple700",
        focused_border_color="purple900"
    )
    
    # Campo para registrar pago de préstamo
    input_pago_monto = ft.TextField(
        label="Monto del pago",
        keyboard_type=ft.KeyboardType.NUMBER,
        color="black",
        text_size=16,
        border_color="purple700",
        focused_border_color="purple900"
    )
    
    # Campos para créditos
    input_credito_desc = ft.TextField(
        label="Descripción de la compra",
        hint_text="Ej: TV, Laptop, Refrigerador...",
        color="black",
        text_size=16,
        border_color="indigo700",
        focused_border_color="indigo900"
    )
    input_credito_banco = ft.TextField(
        label="Banco/Tarjeta",
        hint_text="Ej: BBVA, Santander, Liverpool...",
        color="black",
        text_size=16,
        border_color="indigo700",
        focused_border_color="indigo900"
    )
    input_credito_monto = ft.TextField(
        label="Monto total",
        keyboard_type=ft.KeyboardType.NUMBER,
        color="black",
        text_size=16,
        border_color="indigo700",
        focused_border_color="indigo900"
    )
    input_credito_meses = ft.TextField(
        label="Plazo en meses",
        keyboard_type=ft.KeyboardType.NUMBER,
        color="black",
        text_size=16,
        border_color="indigo700",
        focused_border_color="indigo900"
    )
    input_credito_interes = ft.TextField(
        label="Tasa de interés mensual % (0 = sin intereses)",
        keyboard_type=ft.KeyboardType.NUMBER,
        hint_text="Ej: 0, 2.5, 3.8",
        value="0",
        color="black",
        text_size=16,
        border_color="indigo700",
        focused_border_color="indigo900"
    )
    
    # Campos para ahorros
    input_ahorro_nombre = ft.TextField(
        label="Nombre del ahorro",
        hint_text="Ej: Vacaciones, Auto, Casa...",
        color="black",
        text_size=16,
        border_color="teal700",
        focused_border_color="teal900"
    )
    input_ahorro_meta = ft.TextField(
        label="Meta de ahorro",
        keyboard_type=ft.KeyboardType.NUMBER,
        color="black",
        text_size=16,
        border_color="teal700",
        focused_border_color="teal900"
    )
    
    # Campo para agregar/retirar monto de ahorro
    input_monto_ahorro = ft.TextField(
        label="Monto",
        keyboard_type=ft.KeyboardType.NUMBER,
        color="black",
        text_size=16,
        border_color="teal700",
        focused_border_color="teal900"
    )
    
    # Campos para cuentas bancarias
    input_banco_nombre = ft.TextField(
        label="Nombre del banco",
        hint_text="Ej: BBVA, Santander, Banorte...",
        color="black",
        text_size=16,
        border_color="cyan900",
        focused_border_color="cyan900"
    )
    dropdown_tipo_cuenta = ft.Dropdown(
        label="Tipo de cuenta",
        options=[
            ft.dropdown.Option("debito", "Débito"),
            ft.dropdown.Option("credito", "Crédito"),
            ft.dropdown.Option("ahorro", "Ahorro"),
            ft.dropdown.Option("inversion", "Inversión"),
        ],
        value="debito",
        color="black",
        border_color="cyan900"
    )
    input_banco_saldo = ft.TextField(
        label="Saldo inicial",
        keyboard_type=ft.KeyboardType.NUMBER,
        value="0",
        color="black",
        text_size=16,
        border_color="cyan900",
        focused_border_color="cyan900"
    )
    input_banco_limite = ft.TextField(
        label="Límite de crédito (solo para tarjetas)",
        keyboard_type=ft.KeyboardType.NUMBER,
        value="0",
        color="black",
        text_size=16,
        border_color="cyan900",
        focused_border_color="cyan900"
    )
    
    # Campo para depositar/retirar de cuenta bancaria
    input_monto_banco = ft.TextField(
        label="Monto",
        keyboard_type=ft.KeyboardType.NUMBER,
        color="black",
        text_size=16,
        border_color="cyan900",
        focused_border_color="cyan900"
    )

    # Dialogo para agregar movimiento
    bottom_sheet_movimiento = ft.BottomSheet(
        ft.Container(
            ft.Column(
                [
                    ft.Text("💸 Agregar Movimiento", size=20, weight=ft.FontWeight.BOLD),
                    dropdown_tipo,
                    dropdown_destino_movimiento,
                    dropdown_banco_movimiento,
                    dropdown_cat,
                    input_desc,
                    input_monto,
                    ft.ElevatedButton("Guardar", on_click=guardar_movimiento, width=float("inf"))
                ],
                tight=True,
                spacing=15,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=20,
            border_radius=ft.border_radius.only(top_left=20, top_right=20)
        ),
        is_scroll_controlled=True,
        use_safe_area=True
    )
    
    # Dialogo para agregar suscripción
    bottom_sheet_suscripcion = ft.BottomSheet(
        ft.Container(
            ft.Column(
                [
                    ft.Text("📆 Agregar Suscripción", size=20, weight=ft.FontWeight.BOLD),
                    input_sub_nombre,
                    input_sub_monto,
                    input_sub_dia,
                    ft.ElevatedButton("Guardar", on_click=guardar_suscripcion, width=float("inf"))
                ],
                tight=True,
                spacing=15,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=20,
            border_radius=ft.border_radius.only(top_left=20, top_right=20)
        ),
        is_scroll_controlled=True,
        use_safe_area=True
    )
    
    # Dialogo para agregar préstamo
    bottom_sheet_prestamo = ft.BottomSheet(
        ft.Container(
            ft.Column(
                [
                    ft.Text("🏦 Agregar Préstamo", size=20, weight=ft.FontWeight.BOLD),
                    input_prest_banco,
                    input_prest_monto_total,
                    input_prest_cuota,
                    input_prest_dia,
                    ft.ElevatedButton("Guardar", on_click=guardar_prestamo, width=float("inf"))
                ],
                tight=True,
                spacing=15,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=20,
            border_radius=ft.border_radius.only(top_left=20, top_right=20)
        ),
        is_scroll_controlled=True,
        use_safe_area=True
    )
    
    # Dialogo para agregar compra a crédito
    bottom_sheet_credito = ft.BottomSheet(
        ft.Container(
            ft.Column(
                [
                    ft.Text("💳 Agregar Compra a Crédito", size=20, weight=ft.FontWeight.BOLD),
                    input_credito_desc,
                    input_credito_banco,
                    input_credito_monto,
                    input_credito_meses,
                    input_credito_interes,
                    ft.Text("ℹ️ Si es sin intereses, deja el campo en 0", size=11, color="grey600", italic=True),
                    ft.ElevatedButton("Guardar", on_click=guardar_credito, width=float("inf"))
                ],
                tight=True,
                spacing=12,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=20,
            border_radius=ft.border_radius.only(top_left=20, top_right=20)
        ),
        is_scroll_controlled=True,
        use_safe_area=True
    )
    
    # Variable para almacenar el ID del préstamo al registrar pago
    prestamo_id_pago = [None]
    
    # Dialogo para registrar pago de préstamo
    bottom_sheet_pago_prestamo = ft.BottomSheet(
        ft.Container(
            ft.Column(
                [
                    ft.Text("💳 Registrar Pago", size=20, weight=ft.FontWeight.BOLD),
                    input_pago_monto,
                    ft.ElevatedButton("Confirmar Pago", on_click=lambda e: registrar_pago(e), width=float("inf"))
                ],
                tight=True,
                spacing=15,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=20,
            border_radius=ft.border_radius.only(top_left=20, top_right=20)
        ),
        is_scroll_controlled=True,
        use_safe_area=True
    )
    
    def abrir_registrar_pago(id_prestamo):
        prestamo_id_pago[0] = id_prestamo
        input_pago_monto.value = ""
        input_pago_monto.error_text = None
        bottom_sheet_pago_prestamo.open = True
        page.update()
    
    def registrar_pago(e):
        input_pago_monto.error_text = None
        
        if not input_pago_monto.value:
            input_pago_monto.error_text = "Requerido"
            page.update()
            return
        
        try:
            monto = float(input_pago_monto.value)
        except ValueError:
            input_pago_monto.error_text = "Debe ser un número"
            page.update()
            return
        
        if monto <= 0:
            input_pago_monto.error_text = "Debe ser mayor a 0"
            page.update()
            return
        
        if db.registrar_pago_prestamo(prestamo_id_pago[0], monto):
            input_pago_monto.value = ""
            bottom_sheet_pago_prestamo.open = False
            actualizar_vista()
        else:
            input_pago_monto.error_text = "Error al registrar pago"
            page.update()
    
    # Dialogo para agregar ahorro
    bottom_sheet_ahorro = ft.BottomSheet(
        ft.Container(
            ft.Column(
                [
                    ft.Text("🎯 Crear Meta de Ahorro", size=20, weight=ft.FontWeight.BOLD),
                    input_ahorro_nombre,
                    input_ahorro_meta,
                    ft.ElevatedButton("Crear Meta", on_click=guardar_ahorro, width=float("inf"))
                ],
                tight=True,
                spacing=15,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=20,
            border_radius=ft.border_radius.only(top_left=20, top_right=20)
        ),
        is_scroll_controlled=True,
        use_safe_area=True
    )
    
    # Variable para almacenar el ID del ahorro al agregar/retirar monto
    ahorro_id_operacion = [None]
    operacion_tipo = ["agregar"]  # "agregar" o "retirar"
    
    # Dialogo para agregar/retirar monto de ahorro
    bottom_sheet_monto_ahorro = ft.BottomSheet(
        ft.Container(
            ft.Column(
                [
                    ft.Text("💰 Modificar Ahorro", size=20, weight=ft.FontWeight.BOLD),
                    input_monto_ahorro,
                    ft.ElevatedButton("Confirmar", on_click=lambda e: confirmar_operacion_ahorro(e), width=float("inf"))
                ],
                tight=True,
                spacing=15,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=20,
            border_radius=ft.border_radius.only(top_left=20, top_right=20)
        ),
        is_scroll_controlled=True,
        use_safe_area=True
    )
    
    def abrir_agregar_monto(id_ahorro):
        ahorro_id_operacion[0] = id_ahorro
        operacion_tipo[0] = "agregar"
        input_monto_ahorro.value = ""
        input_monto_ahorro.error_text = None
        input_monto_ahorro.label = "Monto a agregar"
        bottom_sheet_monto_ahorro.open = True
        page.update()
    
    def abrir_retirar_monto(id_ahorro):
        ahorro_id_operacion[0] = id_ahorro
        operacion_tipo[0] = "retirar"
        input_monto_ahorro.value = ""
        input_monto_ahorro.error_text = None
        input_monto_ahorro.label = "Monto a retirar"
        bottom_sheet_monto_ahorro.open = True
        page.update()
    
    def confirmar_operacion_ahorro(e):
        input_monto_ahorro.error_text = None
        
        if not input_monto_ahorro.value:
            input_monto_ahorro.error_text = "Requerido"
            page.update()
            return
        
        try:
            monto = float(input_monto_ahorro.value)
        except ValueError:
            input_monto_ahorro.error_text = "Debe ser un número"
            page.update()
            return
        
        if monto <= 0:
            input_monto_ahorro.error_text = "Debe ser mayor a 0"
            page.update()
            return
        
        exito = False
        if operacion_tipo[0] == "agregar":
            exito = db.agregar_monto_ahorro(ahorro_id_operacion[0], monto)
        else:
            exito = db.retirar_monto_ahorro(ahorro_id_operacion[0], monto)
        
        if exito:
            input_monto_ahorro.value = ""
            bottom_sheet_monto_ahorro.open = False
            actualizar_vista()
        else:
            input_monto_ahorro.error_text = "Error en la operación"
            page.update()
    
    # Dialogo para agregar cuenta bancaria
    bottom_sheet_banco = ft.BottomSheet(
        ft.Container(
            ft.Column(
                [
                    ft.Text("🏦 Agregar Cuenta Bancaria", size=20, weight=ft.FontWeight.BOLD),
                    input_banco_nombre,
                    dropdown_tipo_cuenta,
                    input_banco_saldo,
                    input_banco_limite,
                    ft.Text("ℹ️ El límite solo aplica para tarjetas de crédito", size=11, color="grey600", italic=True),
                    ft.ElevatedButton("Guardar", on_click=guardar_cuenta_bancaria, width=float("inf"))
                ],
                tight=True,
                spacing=12,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=20,
            border_radius=ft.border_radius.only(top_left=20, top_right=20)
        ),
        is_scroll_controlled=True,
        use_safe_area=True
    )
    
    # Variable para almacenar el ID de la cuenta al depositar/retirar
    cuenta_id_operacion = [None]
    operacion_tipo_banco = ["depositar"]  # "depositar" o "retirar"
    
    # Dialogo para depositar/retirar de cuenta bancaria
    bottom_sheet_monto_banco = ft.BottomSheet(
        ft.Container(
            ft.Column(
                [
                    ft.Text("💰 Modificar Saldo", size=20, weight=ft.FontWeight.BOLD),
                    input_monto_banco,
                    ft.ElevatedButton("Confirmar", on_click=lambda e: confirmar_operacion_banco(e), width=float("inf"))
                ],
                tight=True,
                spacing=15,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=20,
            border_radius=ft.border_radius.only(top_left=20, top_right=20)
        ),
        is_scroll_controlled=True,
        use_safe_area=True
    )
    
    def abrir_depositar_banco(id_cuenta):
        cuenta_id_operacion[0] = id_cuenta
        operacion_tipo_banco[0] = "depositar"
        input_monto_banco.value = ""
        input_monto_banco.error_text = None
        input_monto_banco.label = "Monto a depositar"
        bottom_sheet_monto_banco.open = True
        page.update()
    
    def abrir_retirar_banco(id_cuenta):
        cuenta_id_operacion[0] = id_cuenta
        operacion_tipo_banco[0] = "retirar"
        input_monto_banco.value = ""
        input_monto_banco.error_text = None
        input_monto_banco.label = "Monto a retirar"
        bottom_sheet_monto_banco.open = True
        page.update()
    
    def confirmar_operacion_banco(e):
        input_monto_banco.error_text = None
        
        if not input_monto_banco.value:
            input_monto_banco.error_text = "Requerido"
            page.update()
            return
        
        try:
            monto = float(input_monto_banco.value)
        except ValueError:
            input_monto_banco.error_text = "Debe ser un número"
            page.update()
            return
        
        if monto <= 0:
            input_monto_banco.error_text = "Debe ser mayor a 0"
            page.update()
            return
        
        exito = False
        if operacion_tipo_banco[0] == "depositar":
            exito = db.agregar_monto_cuenta(cuenta_id_operacion[0], monto)
        else:
            exito = db.retirar_monto_cuenta(cuenta_id_operacion[0], monto)
        
        if exito:
            input_monto_banco.value = ""
            bottom_sheet_monto_banco.open = False
            actualizar_vista()
        else:
            input_monto_banco.error_text = "Error en la operación"
            page.update()

    def abrir_agregar(e):
        nonlocal vista_actual
        
        if vista_actual == "suscripciones":
            # Limpiar campos de suscripción
            input_sub_nombre.value = ""
            input_sub_monto.value = ""
            input_sub_dia.value = ""
            input_sub_nombre.error_text = None
            input_sub_monto.error_text = None
            input_sub_dia.error_text = None
            bottom_sheet_suscripcion.open = True
        elif vista_actual == "prestamos":
            # Limpiar campos de préstamo
            input_prest_banco.value = ""
            input_prest_monto_total.value = ""
            input_prest_cuota.value = ""
            input_prest_dia.value = ""
            input_prest_banco.error_text = None
            input_prest_monto_total.error_text = None
            input_prest_cuota.error_text = None
            input_prest_dia.error_text = None
            bottom_sheet_prestamo.open = True
        elif vista_actual == "creditos":
            # Limpiar campos de crédito
            input_credito_desc.value = ""
            input_credito_banco.value = ""
            input_credito_monto.value = ""
            input_credito_meses.value = ""
            input_credito_interes.value = "0"
            input_credito_desc.error_text = None
            input_credito_banco.error_text = None
            input_credito_monto.error_text = None
            input_credito_meses.error_text = None
            input_credito_interes.error_text = None
            bottom_sheet_credito.open = True
        elif vista_actual == "ahorros":
            # Limpiar campos de ahorro
            input_ahorro_nombre.value = ""
            input_ahorro_meta.value = ""
            input_ahorro_nombre.error_text = None
            input_ahorro_meta.error_text = None
            bottom_sheet_ahorro.open = True
        elif vista_actual == "bancos":
            # Limpiar campos de cuenta bancaria
            input_banco_nombre.value = ""
            input_banco_saldo.value = "0"
            input_banco_limite.value = "0"
            dropdown_tipo_cuenta.value = "debito"
            input_banco_nombre.error_text = None
            input_banco_saldo.error_text = None
            input_banco_limite.error_text = None
            bottom_sheet_banco.open = True
        else:
            # Limpiar campos de movimiento
            input_desc.value = ""
            input_monto.value = ""
            input_desc.error_text = None
            input_monto.error_text = None
            dropdown_tipo.value = "gasto"
            dropdown_cat.value = "Comida"
            dropdown_destino_movimiento.value = "efectivo"
            dropdown_banco_movimiento.visible = False
            actualizar_opciones_destino()
            bottom_sheet_movimiento.open = True
        
        page.update()

    # Barra superior
    page.appbar = ft.AppBar(
        title=ft.Text("💰 Mis Finanzas", color="white", size=20),
        center_title=True,
        bgcolor="blue700",
        elevation=2
    )

    # Barra de navegación inferior
    page.navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon="home"),
            ft.NavigationBarDestination(icon="subscriptions"),
            ft.NavigationBarDestination(icon="account_balance"),
            ft.NavigationBarDestination(icon="credit_card"),
            ft.NavigationBarDestination(icon="savings"),
            ft.NavigationBarDestination(icon="account_balance_wallet"),
            ft.NavigationBarDestination(icon="bar_chart"),
        ],
        on_change=cambiar_vista,
        selected_index=0
    )

    # Botón Flotante
    page.floating_action_button = ft.FloatingActionButton(
        icon="add",
        bgcolor="blue700",
        on_click=abrir_agregar
    )

    # Agregar BottomSheets al overlay
    page.overlay.append(bottom_sheet_movimiento)
    page.overlay.append(bottom_sheet_suscripcion)
    page.overlay.append(bottom_sheet_prestamo)
    page.overlay.append(bottom_sheet_pago_prestamo)
    page.overlay.append(bottom_sheet_credito)
    page.overlay.append(bottom_sheet_ahorro)
    page.overlay.append(bottom_sheet_monto_ahorro)
    page.overlay.append(bottom_sheet_banco)
    page.overlay.append(bottom_sheet_monto_banco)
    
    # Agregar contenedor principal
    page.add(contenedor_principal)

    # Carga inicial
    actualizar_vista()

# Ejecutar la app
# Para APK móvil, usar view=ft.AppView.FLET_APP
# Para web, usar view=ft.AppView.WEB_BROWSER
ft.app(target=main, view=ft.AppView.FLET_APP)