import flet as ft
import sqlite3
import datetime

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
    vista_actual = "inicio"  # "inicio", "suscripciones", "balance" 

    # --- Componentes de UI ---
    
    # Texto del Balance
    txt_balance_total = ft.Text("$0", size=36, weight=ft.FontWeight.BOLD)
    txt_ingresos = ft.Text("$0", color="green", size=16, weight=ft.FontWeight.BOLD)
    txt_gastos = ft.Text("$0", color="red", size=16, weight=ft.FontWeight.BOLD)
    txt_suscripciones = ft.Text("$0", color="orange", size=16, weight=ft.FontWeight.BOLD)
    txt_disponible = ft.Text("$0", size=20, weight=ft.FontWeight.BOLD, color="blue700")

    # Contenedores para diferentes vistas
    contenedor_principal = ft.Column(spacing=0, expand=True)

    # Campos para agregar nuevo movimiento
    input_desc = ft.TextField(label="Descripción", hint_text="Ej: Supermercado")
    input_monto = ft.TextField(label="Monto", keyboard_type=ft.KeyboardType.NUMBER)
    dropdown_tipo = ft.Dropdown(
        label="Tipo",
        options=[ft.dropdown.Option("gasto"), ft.dropdown.Option("ingreso")],
        value="gasto"
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

    # --- Funciones de Lógica ---

    def actualizar_balance():
        """Actualiza los textos del balance"""
        ingresos, gastos, total = db.obtener_balance()
        total_suscripciones = db.obtener_total_suscripciones()
        disponible = total - total_suscripciones
        
        txt_balance_total.value = f"${total:,.0f}"
        txt_ingresos.value = f"${ingresos:,.0f}"
        txt_gastos.value = f"${gastos:,.0f}"
        txt_suscripciones.value = f"${total_suscripciones:,.0f}"
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
    
    def crear_vista_balance_mensual():
        """Crea la vista de balance mensual"""
        ahora = datetime.datetime.now()
        mes_actual = ahora.month
        anio_actual = ahora.year
        
        ingresos_mes, gastos_mes = db.obtener_balance_mensual(mes_actual, anio_actual)
        total_subs = db.obtener_total_suscripciones()
        balance_mes = ingresos_mes - gastos_mes - total_subs
        
        meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        mes_nombre = meses[mes_actual - 1]
        
        return ft.Column([
            ft.Container(
                content=ft.Column([
                    ft.Text(f"📊 Balance de {mes_nombre} {anio_actual}", size=20, weight=ft.FontWeight.BOLD),
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
            # Limpiar campos y cerrar diálogo
            input_desc.value = ""
            input_monto.value = ""
            input_desc.error_text = None
            input_monto.error_text = None
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

    def borrar_movimiento(id_mov):
        if db.borrar_movimiento(id_mov):
            actualizar_vista()
    
    def borrar_suscripcion(id_sub):
        if db.borrar_suscripcion(id_sub):
            actualizar_vista()

    def cambiar_vista(e):
        nonlocal vista_actual
        vista_actual = ["inicio", "suscripciones", "balance"][e.control.selected_index]
        actualizar_vista()

    # --- Elementos de Navegación y Estructura ---
    
    # Campos para suscripciones
    input_sub_nombre = ft.TextField(label="Nombre", hint_text="Ej: Netflix, Spotify...")
    input_sub_monto = ft.TextField(label="Monto mensual", keyboard_type=ft.KeyboardType.NUMBER)
    input_sub_dia = ft.TextField(label="Día de cobro (1-31)", keyboard_type=ft.KeyboardType.NUMBER)

    # Dialogo para agregar movimiento
    bottom_sheet_movimiento = ft.BottomSheet(
        ft.Container(
            ft.Column(
                [
                    ft.Text("💸 Agregar Movimiento", size=20, weight=ft.FontWeight.BOLD),
                    dropdown_tipo,
                    dropdown_cat,
                    input_desc,
                    input_monto,
                    ft.ElevatedButton("Guardar", on_click=guardar_movimiento, width=float("inf"))
                ],
                tight=True,
                spacing=15
            ),
            padding=20,
            border_radius=ft.border_radius.only(top_left=20, top_right=20)
        )
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
                spacing=15
            ),
            padding=20,
            border_radius=ft.border_radius.only(top_left=20, top_right=20)
        )
    )

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
        else:
            # Limpiar campos de movimiento
            input_desc.value = ""
            input_monto.value = ""
            input_desc.error_text = None
            input_monto.error_text = None
            dropdown_tipo.value = "gasto"
            dropdown_cat.value = "Comida"
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
            ft.NavigationBarDestination(icon="home", label="Inicio"),
            ft.NavigationBarDestination(icon="subscriptions", label="Suscripciones"),
            ft.NavigationBarDestination(icon="bar_chart", label="Balance"),
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
    
    # Agregar contenedor principal
    page.add(contenedor_principal)

    # Carga inicial
    actualizar_vista()

# Ejecutar la app
# Para APK móvil, usar view=ft.AppView.FLET_APP
# Para web, usar view=ft.AppView.WEB_BROWSER
ft.app(target=main, view=ft.AppView.FLET_APP)