import sqlite3
import os

DB_PATH = "barberia.db"

def get_connection():
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
        FOREIGN KEY (barbero_id) REFERENCES barberos (id)
    )
    """)
    
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
        
        conn.commit()
        print("Datos de prueba (seed) cargados exitosamente.")
    else:
        print("La base de datos ya contiene datos. Se omitió la carga de seed.")
        
    conn.close()

if __name__ == '__main__':
    init_db()
    seed_db()
