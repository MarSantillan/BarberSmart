import sqlite3
import os
import re

DB_PATH = "barberia.db"

class PostgresCursorWrapper:
    def __init__(self, pg_cursor):
        self.cursor = pg_cursor
        
    def execute(self, query, params=None):
        # 1. Reemplazar marcadores de parámetros SQLite (?) con Postgres (%s)
        query = query.replace('?', '%s')
        
        # 2. Reemplazar strftime('%Y-%m', campo) con SUBSTR(campo, 1, 7)
        query = re.sub(r"strftime\(\s*'%Y-%m'\s*,\s*([a-zA-Z0-9_\.]+)\s*\)", r"SUBSTR(\1, 1, 7)", query)
        
        # 3. Reemplazar SQLite AUTOINCREMENT con Postgres SERIAL
        query = query.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        
        if params is not None:
            self.cursor.execute(query, params)
        else:
            self.cursor.execute(query)
            
    def executemany(self, query, seq_of_parameters):
        # 1. Reemplazar marcadores (?) con (%s)
        query = query.replace('?', '%s')
        
        # 2. Reemplazar strftime con SUBSTR
        query = re.sub(r"strftime\(\s*'%Y-%m'\s*,\s*([a-zA-Z0-9_\.]+)\s*\)", r"SUBSTR(\1, 1, 7)", query)
        
        # 3. Reemplazar autoincremento
        query = query.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        
        self.cursor.executemany(query, seq_of_parameters)
        
    def __getattr__(self, name):
        return getattr(self.cursor, name)

class PostgresConnectionWrapper:
    def __init__(self, pg_conn):
        self.conn = pg_conn
        
    def cursor(self):
        return PostgresCursorWrapper(self.conn.cursor())
        
    def commit(self):
        self.conn.commit()
        
    def rollback(self):
        self.conn.rollback()
        
    def close(self):
        self.conn.close()
        
    def __getattr__(self, name):
        return getattr(self.conn, name)

def get_connection():
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        try:
            import psycopg2
            pg_conn = psycopg2.connect(db_url)
            return PostgresConnectionWrapper(pg_conn)
        except ImportError:
            print("ERROR: DATABASE_URL está configurada pero psycopg2 no está instalado en el sistema. Usando base local SQLite...")
        except Exception as e:
            print(f"ERROR al conectar a PostgreSQL: {e}. Cayendo en base local SQLite...")
            
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Tabla de barberos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS barberos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        telefono TEXT,
        comision_base REAL DEFAULT 50.0
    )
    """)
    
    # 2. Tabla de turnos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS turnos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_nombre TEXT NOT NULL,
        cliente_telefono TEXT NOT NULL,
        barbero_id INTEGER,
        fecha_hora TEXT NOT NULL, -- Formato: YYYY-MM-DD HH:MM
        estado TEXT DEFAULT 'Pendiente', -- Pendiente, Confirmado, Cancelado, Realizado
        recordatorio_24h_enviado INTEGER DEFAULT 0,
        recordatorio_1h_enviado INTEGER DEFAULT 0,
        FOREIGN KEY (barbero_id) REFERENCES barberos (id)
    )
    """)
    
    conn.commit()
    
    # Agregar columnas si no existen (migración segura para bases existentes)
    for col in [("recordatorio_24h_enviado", "INTEGER DEFAULT 0"), ("recordatorio_1h_enviado", "INTEGER DEFAULT 0")]:
        try:
            cursor.execute(f"ALTER TABLE turnos ADD COLUMN {col[0]} {col[1]}")
            conn.commit()
        except Exception:
            conn.rollback()
    
    # 3. Tabla de insumos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS insumos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        ml_totales REAL NOT NULL,
        ml_actuales REAL NOT NULL,
        precio_compra REAL NOT NULL,
        fecha_compra TEXT NOT NULL -- Formato: YYYY-MM-DD
    )
    """)
    
    # 4. Tabla de servicios realizados
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS servicios_realizados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        turno_id INTEGER,
        barbero_id INTEGER NOT NULL,
        servicio_nombre TEXT NOT NULL,
        monto_cobrado REAL NOT NULL,
        metodo_pago TEXT NOT NULL, -- Efectivo, Transferencia, Tarjeta
        descuento_aplicado REAL DEFAULT 0.0,
        propina_digital REAL DEFAULT 0.0,
        ml_consumidos REAL DEFAULT 0.0,
        insumo_id INTEGER,
        fecha TEXT NOT NULL, -- Formato: YYYY-MM-DD
        aprobado INTEGER DEFAULT 0, -- 0: Pendiente de auditoría, 1: Aprobado por Admin
        FOREIGN KEY (turno_id) REFERENCES turnos (id),
        FOREIGN KEY (barbero_id) REFERENCES barberos (id),
        FOREIGN KEY (insumo_id) REFERENCES insumos (id)
    )
    """)
    
    # 5. Tabla de gastos fijos mensuales
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gastos_fijos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        concepto TEXT NOT NULL,
        monto REAL NOT NULL,
        mes_ano TEXT NOT NULL -- Formato: YYYY-MM
    )
    """)
    
    # 6. Tabla de inversión inicial
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inversion_inicial (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rubro TEXT NOT NULL, -- Mobiliario, Infraestructura, Herramientas, etc.
        detalle TEXT NOT NULL,
        monto_pesos REAL NOT NULL
    )
    """)
    
    # 7. Tabla de amortizaciones
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS amortizaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mes_ano TEXT NOT NULL, -- Formato: YYYY-MM
        monto_amortizado REAL NOT NULL,
        saldo_pendiente REAL NOT NULL
    )
    """)
    
    # 8. Tabla de usuarios para roles
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL, -- admin, barber
        barbero_id INTEGER,
        FOREIGN KEY (barbero_id) REFERENCES barberos (id)
    )
    """)
    
    # 9. Tabla de estados de chat para reservas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_states (
        phone TEXT PRIMARY KEY,
        state TEXT NOT NULL,
        cliente_nombre TEXT,
        barbero_id INTEGER,
        servicio_nombre TEXT,
        fecha TEXT,
        hora TEXT,
        updated_at TEXT
    )
    """)
    
    # 10. Tabla de insumos por servicio realizado (soporte multiproducto)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS servicio_insumos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        servicio_id INTEGER NOT NULL,
        insumo_id INTEGER NOT NULL,
        ml_consumidos REAL NOT NULL,
        FOREIGN KEY (servicio_id) REFERENCES servicios_realizados (id) ON DELETE CASCADE,
        FOREIGN KEY (insumo_id) REFERENCES insumos (id)
    )
    """)
    
    # 11. Tabla de servicios ofrecidos y precios
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS servicios_ofrecidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE,
        precio REAL NOT NULL,
        gasta_insumo INTEGER DEFAULT 0
    )
    """)
    
    # Migración: Agregar columna gasta_insumo si no existe
    try:
        cursor.execute("ALTER TABLE servicios_ofrecidos ADD COLUMN gasta_insumo INTEGER DEFAULT 0")
    except Exception:
        pass
        
    # Migración: Actualizar por defecto servicios de tintura existentes
    try:
        cursor.execute("UPDATE servicios_ofrecidos SET gasta_insumo = 1 WHERE nombre LIKE '%Tintura%'")
    except Exception:
        pass
        
    conn.commit()
    conn.close()
    print("Base de datos inicializada correctamente.")

def seed_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Validar si ya hay datos para evitar duplicados
    cursor.execute("SELECT COUNT(*) FROM barberos")
    if cursor.fetchone()[0] == 0:
        # Cargar barberos
        cursor.execute("INSERT INTO barberos (nombre, telefono, comision_base) VALUES ('Lucas', '1122334455', 50.0)")
        cursor.execute("INSERT INTO barberos (nombre, telefono, comision_base) VALUES ('Martín', '1166778899', 50.0)")
        
        # Cargar inversión inicial
        inversiones = [
            ('Infraestructura', 'Depósito y pintura de local', 150000.0),
            ('Mobiliario', 'Sillones de barbería y espejos premium', 300000.0),
            ('Mobiliario', 'Iluminación LED y cartelería exterior', 80000.0),
            ('Herramientas', 'Secadores, patilleras y tijeras profesionales', 120000.0)
        ]
        cursor.executemany("INSERT INTO inversion_inicial (rubro, detalle, monto_pesos) VALUES (?, ?, ?)", inversiones)
        
        # Cargar insumos iniciales
        insumos = [
            ('Tintura Negra Premium 1', 250.0, 250.0, 4500.0, '2026-06-01'),
            ('Tintura Castaño Oscuro', 250.0, 250.0, 4500.0, '2026-06-01'),
            ('Champú de Ortiga 1L', 1000.0, 1000.0, 8000.0, '2026-06-01'),
            ('Loción Post Afeitado Menta', 500.0, 500.0, 6000.0, '2026-06-02')
        ]
        cursor.executemany("INSERT INTO insumos (nombre, ml_totales, ml_actuales, precio_compra, fecha_compra) VALUES (?, ?, ?, ?, ?)", insumos)
        
        # Cargar gastos fijos mensuales para Junio 2026
        gastos = [
            ('Alquiler de local comercial', 120000.0, '2026-06'),
            ('Luz, agua y servicios', 35000.0, '2026-06'),
            ('Suscripción internet y telefonía', 15000.0, '2026-06')
        ]
        cursor.executemany("INSERT INTO gastos_fijos (concepto, monto, mes_ano) VALUES (?, ?, ?)", gastos)
        
        # Cargar usuarios
        usuarios = [
            ('admin', 'admin123', 'admin', None),
            ('lucas', 'lucas123', 'barber', 1),
            ('martin', 'martin123', 'barber', 2)
        ]
        cursor.executemany("INSERT INTO usuarios (username, password, role, barbero_id) VALUES (?, ?, ?, ?)", usuarios)
        
        # Cargar servicios iniciales (para probar auditoría contable)
        servicios_iniciales = [
            (None, 1, 'Corte de pelo', 5000.0, 'Efectivo', 0.0, 0.0, 0.0, None, '2026-06-20', 1), # Aprobado
            (None, 1, 'Corte y Barba', 7000.0, 'Transferencia', 0.0, 0.0, 0.0, None, '2026-06-21', 1), # Aprobado
            (None, 2, 'Tintura Negra', 12000.0, 'Tarjeta', 0.0, 0.0, 50.0, 1, '2026-06-22', 0), # Pendiente
            (None, 2, 'Corte de pelo', 5000.0, 'Efectivo', 0.0, 0.0, 0.0, None, '2026-06-23', 0) # Pendiente
        ]
        cursor.executemany("""
        INSERT INTO servicios_realizados (turno_id, barbero_id, servicio_nombre, monto_cobrado, metodo_pago, descuento_aplicado, propina_digital, ml_consumidos, insumo_id, fecha, aprobado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, servicios_iniciales)
        
        conn.commit()
        print("Datos de prueba (seed) cargados exitosamente.")
    else:
        print("La base de datos ya contiene datos. Se omitió la carga de seed.")
        
    # Seed de servicios ofrecidos independientemente
    cursor.execute("SELECT COUNT(*) FROM servicios_ofrecidos")
    if cursor.fetchone()[0] == 0:
        servicios_defecto = [
            ('Corte de pelo', 5000.0, 0),
            ('Recorte de barba', 3000.0, 0),
            ('Corte y Barba', 7000.0, 0),
            ('Tintura Negra', 12000.0, 1),
            ('Tintura Castaño', 12000.0, 1)
        ]
        cursor.executemany("INSERT INTO servicios_ofrecidos (nombre, precio, gasta_insumo) VALUES (?, ?, ?)", servicios_defecto)
        conn.commit()
        print("Servicios ofrecidos inicializados por defecto.")
        
    conn.close()

if __name__ == '__main__':
    init_db()
    seed_db()
