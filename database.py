# database.py - Módulo de base de datos para JFinanzas
import sqlite3
import datetime
import hashlib
import json
import hmac
import secrets


class Database:
    def __init__(self, db_path="finanzas.db"):
        self.db_path = db_path
        # Nunca sustituir silenciosamente la base persistente por una temporal:
        # eso haría que la app pareciera funcionar mientras pierde los datos al cerrarse.
        self.conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10)
        self.create_table()

    def create_table(self):
        cursor = self.conn.cursor()
        # Tabla de configuración de la app
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS configuracion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clave TEXT UNIQUE NOT NULL,
                valor TEXT
            )
        """)
        # Tabla de presupuestos por categoría
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS presupuestos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                categoria TEXT UNIQUE NOT NULL,
                limite REAL NOT NULL,
                mes INTEGER,
                anio INTEGER
            )
        """)
        # Tabla de movimientos (solo personal)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT,
                categoria TEXT,
                monto REAL,
                descripcion TEXT,
                fecha TEXT,
                medio_pago TEXT NOT NULL DEFAULT 'efectivo',
                cuenta_bancaria_id INTEGER,
                credito_id INTEGER
            )
        """)
        # Tabla de suscripciones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS suscripciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                monto REAL NOT NULL,
                dia_cobro INTEGER,
                activa INTEGER DEFAULT 1
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
                dia_pago INTEGER,
                fecha_inicio TEXT,
                activo INTEGER DEFAULT 1
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
                completado INTEGER DEFAULT 0
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
                tasa_interes REAL DEFAULT 0,
                pagado INTEGER DEFAULT 0,
                cuenta_bancaria_id INTEGER,
                movimiento_id INTEGER
            )
        """)
        # Tabla de cuentas bancarias
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cuentas_bancarias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_banco TEXT NOT NULL,
                tipo_cuenta TEXT NOT NULL,
                saldo REAL DEFAULT 0,
                limite_credito REAL DEFAULT 0,
                fecha_creacion TEXT,
                activa INTEGER DEFAULT 1
            )
        """)
        # Tabla de transferencias entre cuentas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transferencias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cuenta_origen INTEGER,
                cuenta_destino INTEGER,
                monto REAL NOT NULL,
                fecha TEXT,
                descripcion TEXT,
                credito_id INTEGER,
                FOREIGN KEY (cuenta_origen) REFERENCES cuentas_bancarias(id),
                FOREIGN KEY (cuenta_destino) REFERENCES cuentas_bancarias(id)
            )
        """)
        # Migración aditiva para conservar las bases de datos ya existentes.
        columnas_nuevas = {
            "movimientos": {
                # NULL conserva el desconocimiento del medio de pago de los registros viejos.
                "medio_pago": "TEXT",
                "cuenta_bancaria_id": "INTEGER",
                "credito_id": "INTEGER",
            },
            "creditos": {
                "cuenta_bancaria_id": "INTEGER",
                "movimiento_id": "INTEGER",
            },
            "transferencias": {
                "credito_id": "INTEGER",
            },
        }
        for tabla, columnas in columnas_nuevas.items():
            cursor.execute(f"PRAGMA table_info({tabla})")
            existentes = {fila[1] for fila in cursor.fetchall()}
            for columna, definicion in columnas.items():
                if columna not in existentes:
                    cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")

        self.conn.commit()
    
    # --- Métodos de Configuración ---
    
    def obtener_config(self, clave, default=None):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT valor FROM configuracion WHERE clave = ?", (clave,))
            result = cursor.fetchone()
            return result[0] if result else default
        except:
            return default
    
    def guardar_config(self, clave, valor):
        try:
            cursor = self.conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES (?, ?)", (clave, valor))
            self.conn.commit()
            return True
        except:
            return False
    
    def verificar_pin(self, pin):
        pin_guardado = self.obtener_config("pin_hash")
        if not pin_guardado:
            return True
        bloqueado_hasta = float(self.obtener_config("pin_bloqueado_hasta", "0") or 0)
        ahora = datetime.datetime.now().timestamp()
        if ahora < bloqueado_hasta:
            return False
        if pin_guardado.startswith("pbkdf2_sha256$"):
            _, iteraciones, sal, hash_guardado = pin_guardado.split("$", 3)
            hash_calculado = hashlib.pbkdf2_hmac(
                "sha256", pin.encode(), bytes.fromhex(sal), int(iteraciones)
            ).hex()
            correcto = hmac.compare_digest(hash_calculado, hash_guardado)
        else:
            # Mantiene compatibilidad con los PIN SHA-256 guardados por versiones anteriores.
            correcto = hmac.compare_digest(hashlib.sha256(pin.encode()).hexdigest(), pin_guardado)
            if correcto:
                self.guardar_pin(pin)
        intentos = int(self.obtener_config("pin_intentos", "0") or 0)
        if correcto:
            self.guardar_config("pin_intentos", "0")
            self.guardar_config("pin_bloqueado_hasta", "0")
            return True
        intentos += 1
        if intentos >= 5:
            self.guardar_config("pin_intentos", "0")
            self.guardar_config("pin_bloqueado_hasta", str(ahora + 30))
        else:
            self.guardar_config("pin_intentos", str(intentos))
        return False
    
    def guardar_pin(self, pin):
        sal = secrets.token_bytes(16)
        iteraciones = 310000
        hash_pin = hashlib.pbkdf2_hmac("sha256", pin.encode(), sal, iteraciones).hex()
        pin_guardado = f"pbkdf2_sha256${iteraciones}${sal.hex()}${hash_pin}"
        return self.guardar_config("pin_hash", pin_guardado)
    
    def tiene_pin(self):
        return self.obtener_config("pin_hash") is not None
    
    def es_primera_vez(self):
        return self.obtener_config("onboarding_completado") != "1"
    
    def completar_onboarding(self):
        return self.guardar_config("onboarding_completado", "1")
    
    def obtener_tema(self):
        return self.obtener_config("tema", "light")
    
    def guardar_tema(self, tema):
        return self.guardar_config("tema", tema)
    
    # --- Métodos de Presupuestos ---
    
    def agregar_presupuesto(self, categoria, limite):
        try:
            cursor = self.conn.cursor()
            ahora = datetime.datetime.now()
            cursor.execute("""
                INSERT OR REPLACE INTO presupuestos (categoria, limite, mes, anio) 
                VALUES (?, ?, ?, ?)
            """, (categoria, limite, ahora.month, ahora.year))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error al agregar presupuesto: {e}")
            return False
    
    def obtener_presupuestos(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM presupuestos ORDER BY categoria")
            return cursor.fetchall()
        except:
            return []
    
    def obtener_gasto_categoria_mes(self, categoria, mes=None, anio=None):
        try:
            if mes is None:
                mes = datetime.datetime.now().month
            if anio is None:
                anio = datetime.datetime.now().year
            
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT SUM(monto) FROM movimientos 
                WHERE tipo = 'gasto' AND categoria = ? 
                AND strftime('%m', fecha) = ? AND strftime('%Y', fecha) = ?
            """, (categoria, f"{mes:02d}", str(anio)))
            result = cursor.fetchone()[0]
            return result if result else 0
        except:
            return 0
    
    def borrar_presupuesto(self, id_presupuesto):
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM presupuestos WHERE id = ?", (id_presupuesto,))
            self.conn.commit()
            return True
        except:
            return False
    
    # --- Métodos de Transferencias ---
    
    def realizar_transferencia(self, cuenta_origen, cuenta_destino, monto, descripcion=""):
        try:
            cursor = self.conn.cursor()
            if monto <= 0 or cuenta_origen == cuenta_destino:
                return False
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("SELECT tipo_cuenta FROM cuentas_bancarias WHERE id = ? AND activa = 1", (cuenta_origen,))
            origen = cursor.fetchone()
            cursor.execute("SELECT tipo_cuenta FROM cuentas_bancarias WHERE id = ? AND activa = 1", (cuenta_destino,))
            destino = cursor.fetchone()
            if not origen or not destino or origen[0] == "credito" or destino[0] == "credito":
                self.conn.rollback()
                return False
            cursor.execute("UPDATE cuentas_bancarias SET saldo = saldo - ? WHERE id = ?", (monto, cuenta_origen))
            cursor.execute("UPDATE cuentas_bancarias SET saldo = saldo + ? WHERE id = ?", (monto, cuenta_destino))
            fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            cursor.execute("""
                INSERT INTO transferencias (cuenta_origen, cuenta_destino, monto, fecha, descripcion)
                VALUES (?, ?, ?, ?, ?)
            """, (cuenta_origen, cuenta_destino, monto, fecha, descripcion))
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            print(f"Error en transferencia: {e}")
            return False
    
    def obtener_transferencias(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT t.id, c1.nombre_banco, c2.nombre_banco, t.monto, t.fecha, t.descripcion
                FROM transferencias t
                LEFT JOIN cuentas_bancarias c1 ON t.cuenta_origen = c1.id
                LEFT JOIN cuentas_bancarias c2 ON t.cuenta_destino = c2.id
                ORDER BY t.fecha DESC
            """)
            return cursor.fetchall()
        except:
            return []
    
    # --- Métodos de Estadísticas para Gráficos ---
    
    def obtener_gastos_por_categoria(self, mes=None, anio=None):
        try:
            if mes is None:
                mes = datetime.datetime.now().month
            if anio is None:
                anio = datetime.datetime.now().year
            
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT categoria, SUM(monto) as total
                FROM movimientos 
                WHERE tipo = 'gasto' 
                AND strftime('%m', fecha) = ? AND strftime('%Y', fecha) = ?
                GROUP BY categoria
                ORDER BY total DESC
            """, (f"{mes:02d}", str(anio)))
            return cursor.fetchall()
        except:
            return []
    
    def obtener_balance_ultimos_meses(self, num_meses=6):
        try:
            resultados = []
            ahora = datetime.datetime.now()
            
            for i in range(num_meses - 1, -1, -1):
                fecha = ahora - datetime.timedelta(days=i*30)
                mes = fecha.month
                anio = fecha.year
                
                ingresos, gastos = self.obtener_balance_mensual(mes, anio)
                resultados.append({
                    "mes": fecha.strftime("%b"),
                    "anio": anio,
                    "ingresos": ingresos,
                    "gastos": gastos
                })
            
            return resultados
        except:
            return []
    
    # --- Métodos de Edición ---
    
    def editar_movimiento(self, id_mov, tipo, categoria, monto, descripcion):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE movimientos SET tipo = ?, categoria = ?, monto = ?, descripcion = ?
                WHERE id = ?
            """, (tipo, categoria, monto, descripcion, id_mov))
            self.conn.commit()
            return True
        except:
            return False
    
    def editar_suscripcion(self, id_sub, nombre, monto, dia_cobro):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE suscripciones SET nombre = ?, monto = ?, dia_cobro = ?
                WHERE id = ?
            """, (nombre, monto, dia_cobro, id_sub))
            self.conn.commit()
            return True
        except:
            return False
    
    def editar_prestamo(self, id_pres, banco, monto_total, cuota_mensual, dia_pago):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE prestamos SET banco = ?, monto_total = ?, cuota_mensual = ?, dia_pago = ?
                WHERE id = ?
            """, (banco, monto_total, cuota_mensual, dia_pago, id_pres))
            self.conn.commit()
            return True
        except:
            return False
    
    def editar_ahorro(self, id_aho, nombre, meta):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE ahorros SET nombre = ?, meta = ?
                WHERE id = ?
            """, (nombre, meta, id_aho))
            self.conn.commit()
            return True
        except:
            return False
    
    def editar_credito(self, id_cred, descripcion, banco, monto_total, meses_plazo, tasa_interes):
        try:
            cursor = self.conn.cursor()
            if tasa_interes > 0:
                tasa_mensual = tasa_interes / 100
                cuota_mensual = monto_total * (tasa_mensual * pow(1 + tasa_mensual, meses_plazo)) / (pow(1 + tasa_mensual, meses_plazo) - 1)
            else:
                cuota_mensual = monto_total / meses_plazo if meses_plazo > 0 else monto_total
            
            cursor.execute("""
                UPDATE creditos SET descripcion = ?, banco = ?, monto_total = ?, 
                meses_sin_intereses = ?, cuota_mensual = ?, tasa_interes = ?
                WHERE id = ?
            """, (descripcion, banco, monto_total, meses_plazo, cuota_mensual, tasa_interes, id_cred))
            self.conn.commit()
            return True
        except:
            return False
    
    def editar_cuenta_bancaria(self, id_cuenta, nombre_banco, tipo_cuenta, limite_credito):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE cuentas_bancarias SET nombre_banco = ?, tipo_cuenta = ?, limite_credito = ?
                WHERE id = ?
            """, (nombre_banco, tipo_cuenta, limite_credito, id_cuenta))
            self.conn.commit()
            return True
        except:
            return False
    
    # --- Métodos de Búsqueda ---
    
    def buscar_movimientos(self, texto="", categoria=None, tipo=None, fecha_desde=None, fecha_hasta=None):
        try:
            cursor = self.conn.cursor()
            query = (
                "SELECT m.id, m.tipo, m.categoria, m.monto, m.descripcion, m.fecha, "
                "m.medio_pago, c.nombre_banco "
                "FROM movimientos m LEFT JOIN cuentas_bancarias c "
                "ON c.id = m.cuenta_bancaria_id WHERE 1=1"
            )
            params = []
            
            if texto:
                query += " AND (m.descripcion LIKE ? OR m.categoria LIKE ?)"
                params.extend([f"%{texto}%", f"%{texto}%"])
            
            if categoria:
                query += " AND m.categoria = ?"
                params.append(categoria)
            
            if tipo:
                query += " AND m.tipo = ?"
                params.append(tipo)
            
            if fecha_desde:
                query += " AND m.fecha >= ?"
                params.append(fecha_desde)
            
            if fecha_hasta:
                query += " AND m.fecha <= ?"
                params.append(fecha_hasta)
            
            query += " ORDER BY m.id DESC"
            cursor.execute(query, params)
            return cursor.fetchall()
        except:
            return []
    
    # --- Backup y Restauración ---
    
    def exportar_datos(self):
        try:
            cursor = self.conn.cursor()
            datos = {}
            
            tablas = ['movimientos', 'suscripciones', 'prestamos', 'ahorros', 'creditos', 'cuentas_bancarias', 'presupuestos', 'transferencias']
            
            for tabla in tablas:
                cursor.execute(f"SELECT * FROM {tabla}")
                columnas = [description[0] for description in cursor.description]
                filas = cursor.fetchall()
                datos[tabla] = [dict(zip(columnas, fila)) for fila in filas]
            
            return json.dumps(datos, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error al exportar: {e}")
            return None
    
    def importar_datos(self, json_data):
        try:
            datos = json.loads(json_data)
            cursor = self.conn.cursor()
            tablas_permitidas = {"movimientos", "suscripciones", "prestamos", "ahorros", "creditos", "cuentas_bancarias", "presupuestos", "transferencias"}
            if not isinstance(datos, dict) or not datos or not set(datos).issubset(tablas_permitidas):
                return False
            cursor.execute("BEGIN IMMEDIATE")
            for tabla, registros in datos.items():
                if not isinstance(registros, list):
                    raise ValueError(f"Formato inválido en {tabla}")
                cursor.execute(f"PRAGMA table_info({tabla})")
                columnas_validas = {fila[1] for fila in cursor.fetchall()}
                for registro in registros:
                    if not isinstance(registro, dict) or not set(registro).issubset(columnas_validas):
                        raise ValueError(f"Registro inválido en {tabla}")
                    columnas = ', '.join(registro.keys())
                    placeholders = ', '.join(['?' for _ in registro])
                    valores = list(registro.values())
                    if not columnas:
                        continue
                    cursor.execute(f"INSERT OR REPLACE INTO {tabla} ({columnas}) VALUES ({placeholders})", valores)
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            print(f"Error al importar: {e}")
            return False

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
            cursor.execute(
                "SELECT m.id, m.tipo, m.categoria, m.monto, m.descripcion, m.fecha, "
                "m.medio_pago, c.nombre_banco "
                "FROM movimientos m LEFT JOIN cuentas_bancarias c "
                "ON c.id = m.cuenta_bancaria_id ORDER BY m.id DESC"
            )
            return cursor.fetchall()
        except Exception as e:
            print(f"Error al obtener movimientos: {e}")
            return []

    def obtener_movimiento_edicion(self, id_movimiento):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT medio_pago, cuenta_bancaria_id, credito_id FROM movimientos WHERE id = ?", (id_movimiento,))
            return cursor.fetchone()
        except Exception:
            return None

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
        try:
            cursor = self.conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute(
                "SELECT tipo, monto, medio_pago, cuenta_bancaria_id, credito_id "
                "FROM movimientos WHERE id = ?",
                (id_movimiento,),
            )
            movimiento = cursor.fetchone()
            if not movimiento:
                self.conn.rollback()
                return False

            tipo, monto, medio_pago, cuenta_id, credito_id = movimiento
            if cuenta_id is not None:
                # Deshacer el efecto bancario del movimiento eliminado.
                delta = -monto if tipo == "ingreso" else monto
                cursor.execute(
                    "UPDATE cuentas_bancarias SET saldo = saldo + ? WHERE id = ?",
                    (delta, cuenta_id),
                )
            if credito_id is not None:
                cursor.execute(
                    "SELECT cuenta_origen, cuenta_destino, monto FROM transferencias "
                    "WHERE credito_id = ?",
                    (credito_id,),
                )
                pagos = cursor.fetchall()
                for cuenta_origen, cuenta_destino, monto_pago in pagos:
                    cursor.execute(
                        "UPDATE cuentas_bancarias SET saldo = saldo + ? WHERE id = ?",
                        (monto_pago, cuenta_origen),
                    )
                    cursor.execute(
                        "UPDATE cuentas_bancarias SET saldo = saldo - ? WHERE id = ?",
                        (monto_pago, cuenta_destino),
                    )
                cursor.execute("DELETE FROM transferencias WHERE credito_id = ?", (credito_id,))
                cursor.execute("UPDATE creditos SET pagado = 1 WHERE id = ?", (credito_id,))

            cursor.execute("DELETE FROM movimientos WHERE id = ?", (id_movimiento,))
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            print(f"Error al borrar movimiento: {e}")
            return False

    def editar_movimiento_financiero(self, id_movimiento, tipo, categoria, monto, descripcion, medio_pago, cuenta_id=None):
        """Actualiza un movimiento y recalcula en una transacción su efecto en cuentas."""
        if tipo not in ("ingreso", "gasto") or monto <= 0 or medio_pago not in ("efectivo", "banco"):
            return False, "Por seguridad, una compra con tarjeta registrada no se puede editar aquí."
        if medio_pago == "banco" and cuenta_id is None:
            return False, "Selecciona una cuenta bancaria."
        try:
            cursor = self.conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("SELECT tipo, monto, cuenta_bancaria_id, credito_id FROM movimientos WHERE id = ?", (id_movimiento,))
            anterior = cursor.fetchone()
            if not anterior:
                raise ValueError("El movimiento ya no existe.")
            tipo_anterior, monto_anterior, cuenta_anterior, credito_anterior = anterior
            if credito_anterior is not None:
                raise ValueError("Las compras con tarjeta se administran desde Créditos y no se pueden editar aquí.")
            if cuenta_id is not None:
                cursor.execute("SELECT tipo_cuenta FROM cuentas_bancarias WHERE id = ? AND activa = 1", (cuenta_id,))
                cuenta = cursor.fetchone()
                if not cuenta or cuenta[0] == "credito":
                    raise ValueError("Selecciona una cuenta bancaria activa.")
            if cuenta_anterior is not None:
                delta_anterior = monto_anterior if tipo_anterior == "gasto" else -monto_anterior
                cursor.execute("UPDATE cuentas_bancarias SET saldo = saldo + ? WHERE id = ?", (delta_anterior, cuenta_anterior))
            if medio_pago == "banco":
                delta_nuevo = -monto if tipo == "gasto" else monto
                cursor.execute("UPDATE cuentas_bancarias SET saldo = saldo + ? WHERE id = ?", (delta_nuevo, cuenta_id))
            cursor.execute("UPDATE movimientos SET tipo=?, categoria=?, monto=?, descripcion=?, medio_pago=?, cuenta_bancaria_id=? WHERE id=?",
                           (tipo, categoria, monto, descripcion, medio_pago, cuenta_id if medio_pago == "banco" else None, id_movimiento))
            self.conn.commit()
            return True, ""
        except ValueError as e:
            self.conn.rollback()
            return False, str(e)
        except Exception as e:
            self.conn.rollback()
            print(f"Error al editar movimiento: {e}")
            return False, "No se pudo actualizar el movimiento."

    def registrar_movimiento_financiero(
        self, tipo, categoria, monto, descripcion, medio_pago="efectivo", cuenta_id=None
    ):
        """Registra movimiento y su efecto bancario/crédito en una transacción."""
        if tipo not in ("ingreso", "gasto") or monto <= 0:
            return False, "El tipo de movimiento o el monto no son válidos."
        if medio_pago not in ("efectivo", "banco", "tarjeta_credito"):
            return False, "Selecciona un método de pago válido."
        if medio_pago == "tarjeta_credito" and tipo != "gasto":
            return False, "Las tarjetas de crédito solo se pueden usar para gastos."
        if medio_pago != "efectivo" and cuenta_id is None:
            return False, "Selecciona una cuenta para este movimiento."

        try:
            cursor = self.conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")

            cuenta = None
            if cuenta_id is not None:
                cursor.execute(
                    "SELECT nombre_banco, tipo_cuenta, saldo, limite_credito "
                    "FROM cuentas_bancarias WHERE id = ? AND activa = 1",
                    (cuenta_id,),
                )
                cuenta = cursor.fetchone()
                if not cuenta:
                    raise ValueError("La cuenta seleccionada ya no está disponible.")

                nombre_cuenta, tipo_cuenta, saldo, limite = cuenta
                saldo = saldo or 0
                limite = limite or 0
                es_tarjeta = tipo_cuenta == "credito"
                if medio_pago == "tarjeta_credito" and not es_tarjeta:
                    raise ValueError("Selecciona una cuenta registrada como tarjeta de crédito.")
                if medio_pago == "banco" and es_tarjeta:
                    raise ValueError("Para pagar con tarjeta, elige el método de tarjeta de crédito.")
                if es_tarjeta and limite > 0 and abs(saldo) + monto > limite:
                    raise ValueError("El gasto supera el crédito disponible de esta tarjeta.")

            fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            cursor.execute(
                "INSERT INTO movimientos "
                "(tipo, categoria, monto, descripcion, fecha, medio_pago, cuenta_bancaria_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (tipo, categoria, monto, descripcion, fecha, medio_pago, cuenta_id),
            )
            movimiento_id = cursor.lastrowid

            if cuenta_id is not None:
                # Ingresos aumentan el saldo; gastos reducen el saldo o crédito disponible.
                if medio_pago == "tarjeta_credito":
                    cursor.execute(
                        "UPDATE cuentas_bancarias SET saldo = -ABS(saldo) - ? WHERE id = ?",
                        (monto, cuenta_id),
                    )
                else:
                    delta = monto if tipo == "ingreso" else -monto
                    cursor.execute(
                        "UPDATE cuentas_bancarias SET saldo = saldo + ? WHERE id = ?",
                        (delta, cuenta_id),
                    )

            if medio_pago == "tarjeta_credito":
                # Compras capturadas desde Inicio se registran por defecto a 1 cuota y 0%.
                cursor.execute(
                    "INSERT INTO creditos "
                    "(descripcion, banco, monto_total, meses_sin_intereses, cuota_mensual, "
                    "fecha_compra, tasa_interes, cuenta_bancaria_id, movimiento_id) "
                    "VALUES (?, ?, ?, 1, ?, ?, 0, ?, ?)",
                    (descripcion, nombre_cuenta, monto, monto, fecha[:10], cuenta_id, movimiento_id),
                )
                credito_id = cursor.lastrowid
                cursor.execute(
                    "UPDATE movimientos SET credito_id = ? WHERE id = ?",
                    (credito_id, movimiento_id),
                )

            self.conn.commit()
            return True, ""
        except ValueError as e:
            self.conn.rollback()
            return False, str(e)
        except Exception as e:
            self.conn.rollback()
            print(f"Error al registrar movimiento financiero: {e}")
            return False, "No se pudo guardar el movimiento. Intenta de nuevo."
    
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
            if tasa_interes > 0:
                tasa_mensual = tasa_interes / 100
                cuota_mensual = monto_total * (tasa_mensual * pow(1 + tasa_mensual, meses_plazo)) / (pow(1 + tasa_mensual, meses_plazo) - 1)
            else:
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
            cursor.execute(
                "SELECT id, descripcion, banco, monto_total, meses_sin_intereses, "
                "cuota_mensual, meses_pagados, fecha_compra, tasa_interes, pagado "
                "FROM creditos WHERE pagado = 0 ORDER BY fecha_compra DESC"
            )
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

    def obtener_cuotas_creditos_no_registradas_como_gasto(self):
        """Cuotas de créditos manuales, que no tienen un gasto asociado."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT SUM(cuota_mensual) FROM creditos "
                "WHERE pagado = 0 AND movimiento_id IS NULL"
            )
            return cursor.fetchone()[0] or 0
        except Exception as e:
            print(f"Error al calcular cuotas no asociadas a gastos: {e}")
            return 0

    def obtener_cuotas_creditos_para_mes(self, mes, anio):
        """No vuelve a descontar en el mes de compra un gasto ya registrado."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT SUM(cuota_mensual) FROM creditos WHERE pagado = 0 AND ("
                "movimiento_id IS NULL OR substr(fecha_compra, 1, 7) != ?) ",
                (f"{anio:04d}-{mes:02d}",),
            )
            return cursor.fetchone()[0] or 0
        except Exception as e:
            print(f"Error al calcular cuotas del mes: {e}")
            return 0

    def obtener_pagos_tarjeta_mes(self, mes, anio):
        """Pagos de tarjeta registrados como transferencias en el mes."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT SUM(monto) FROM transferencias WHERE credito_id IS NOT NULL "
                "AND strftime('%m', fecha) = ? AND strftime('%Y', fecha) = ?",
                (f"{mes:02d}", str(anio)),
            )
            return cursor.fetchone()[0] or 0
        except Exception as e:
            print(f"Error al calcular pagos de tarjeta del mes: {e}")
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
    
    def obtener_info_pago_credito(self, id_credito):
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT descripcion, cuenta_bancaria_id FROM creditos WHERE id = ? AND pagado = 0",
                (id_credito,),
            )
            return cursor.fetchone()
        except Exception as e:
            print(f"Error al consultar el crédito: {e}")
            return None

    def registrar_pago_credito(self, id_credito, cuenta_pago_id=None):
        try:
            cursor = self.conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute(
                "SELECT descripcion, meses_sin_intereses, meses_pagados, cuota_mensual, "
                "cuenta_bancaria_id FROM creditos WHERE id = ? AND pagado = 0",
                (id_credito,),
            )
            result = cursor.fetchone()
            if result:
                descripcion, meses_totales, meses_pagados, cuota, tarjeta_id = result
                nuevos_meses_pagados = meses_pagados + 1

                if tarjeta_id is not None:
                    if cuenta_pago_id is None:
                        self.conn.rollback()
                        return False
                    cursor.execute(
                        "SELECT saldo FROM cuentas_bancarias "
                        "WHERE id = ? AND activa = 1 AND tipo_cuenta != 'credito'",
                        (cuenta_pago_id,),
                    )
                    cuenta_pago = cursor.fetchone()
                    if not cuenta_pago:
                        self.conn.rollback()
                        return False
                    cursor.execute(
                        "SELECT saldo FROM cuentas_bancarias "
                        "WHERE id = ? AND activa = 1 AND tipo_cuenta = 'credito'",
                        (tarjeta_id,),
                    )
                    tarjeta = cursor.fetchone()
                    if not tarjeta:
                        self.conn.rollback()
                        return False

                    fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    cursor.execute(
                        "UPDATE cuentas_bancarias SET saldo = saldo - ? WHERE id = ?",
                        (cuota, cuenta_pago_id),
                    )
                    cursor.execute(
                        "UPDATE cuentas_bancarias SET saldo = saldo + ? WHERE id = ?",
                        (cuota, tarjeta_id),
                    )
                    cursor.execute(
                        "INSERT INTO transferencias "
                        "(cuenta_origen, cuenta_destino, monto, fecha, descripcion, credito_id) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (cuenta_pago_id, tarjeta_id, cuota, fecha, f"Pago de crédito: {descripcion}", id_credito),
                    )
                
                if nuevos_meses_pagados >= meses_totales:
                    cursor.execute("UPDATE creditos SET meses_pagados = ?, pagado = 1 WHERE id = ?", 
                                   (meses_totales, id_credito))
                else:
                    cursor.execute("UPDATE creditos SET meses_pagados = ? WHERE id = ?", 
                                   (nuevos_meses_pagados, id_credito))
                self.conn.commit()
                return True
            self.conn.rollback()
        except Exception as e:
            self.conn.rollback()
            print(f"Error al registrar pago de crédito: {e}")
            return False
    
    def borrar_credito(self, id_credito):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT movimiento_id FROM creditos WHERE id = ?", (id_credito,))
            credito = cursor.fetchone()
            if credito and credito[0] is not None:
                # Si el crédito nació de un gasto de Inicio, eliminarlo también
                # revierte el gasto y el saldo de la tarjeta.
                return self.borrar_movimiento(credito[0])
            cursor.execute("UPDATE creditos SET pagado = 1 WHERE id = ?", (id_credito,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error al borrar crédito: {e}")
            return False
    
    # --- Métodos para Cuentas Bancarias ---
    
    def agregar_cuenta_bancaria(self, nombre_banco, tipo_cuenta, saldo_inicial=0, limite_credito=0):
        try:
            if tipo_cuenta == "credito":
                saldo_inicial = -abs(saldo_inicial)
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
        if self.conn:
            self.conn.close()
