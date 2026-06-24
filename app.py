from flask import Flask, request, jsonify, render_template
import sqlite3
from database import get_connection, init_db, seed_db
from agents_simulator import BookingAgent, FinanceAgent, SupplyAgent
import os

app = Flask(__name__)

# Asegurar que la base de datos esté lista
init_db()
seed_db()

booking_agent = BookingAgent()
finance_agent = FinanceAgent()
supply_agent = SupplyAgent()

@app.route('/')
def home():
    # Retorna la interfaz HTML
    return render_template('index.html')

@app.route('/api/dashboard')
def get_dashboard_data():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Total Inversión Inicial y Amortizaciones
    cursor.execute("SELECT SUM(monto_pesos) FROM inversion_inicial")
    inversion_total = cursor.fetchone()[0] or 0.0
    
    cursor.execute("SELECT SUM(monto_amortizado), saldo_pendiente FROM amortizaciones ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    if row and row[0] is not None:
        total_amortizado = row[0]
        saldo_pendiente = row[1]
    else:
        total_amortizado = 0.0
        saldo_pendiente = inversion_total
        
    # 2. Servicios realizados del mes corriente (Junio 2026 en el simulador)
    mes_ano = "2026-06"
    cursor.execute("SELECT SUM(monto_cobrado) FROM servicios_realizados WHERE strftime('%Y-%m', fecha) = ?", (mes_ano,))
    caja_mensual = cursor.fetchone()[0] or 0.0
    
    # 3. Gastos fijos del mes corriente
    cursor.execute("SELECT SUM(monto) FROM gastos_fijos WHERE mes_ano = ?", (mes_ano,))
    gastos_fijos = cursor.fetchone()[0] or 0.0
    
    # 4. Insumos en stock y alertas
    cursor.execute("SELECT id, nombre, ml_totales, ml_actuales, precio_compra FROM insumos")
    insumos_rows = cursor.fetchall()
    insumos_list = []
    alertas_list = []
    
    for id_i, nombre, ml_tot, ml_act, precio in insumos_rows:
        pct = (ml_act / ml_tot) * 100
        alert = pct < 15.0
        insumos_list.append({
            "id": id_i,
            "nombre": nombre,
            "ml_totales": ml_tot,
            "ml_actuales": ml_act,
            "porcentaje": round(pct, 1),
            "precio_compra": precio,
            "alerta": alert
        })
        if alert:
            alertas_list.append(f"Stock bajo: {nombre} ({ml_act:.1f}ml restantes)")
            
    # 5. Listado de turnos recientes
    cursor.execute("""
    SELECT t.id, t.cliente_nombre, t.fecha_hora, t.estado, b.nombre 
    FROM turnos t 
    JOIN barberos b ON t.barbero_id = b.id
    ORDER BY t.fecha_hora DESC LIMIT 8
    """)
    turnos_list = []
    for t_id, cli_n, fh, est, bar_n in cursor.fetchall():
        turnos_list.append({
            "id": t_id,
            "cliente_nombre": cli_n,
            "fecha_hora": fh,
            "estado": est,
            "barbero_nombre": bar_n
        })
        
    cursor.execute("SELECT id, rubro, detalle, monto_pesos FROM inversion_inicial")
    inversion_items = []
    for item_id, rubro, detalle, monto in cursor.fetchall():
        inversion_items.append({
            "id": item_id,
            "rubro": rubro,
            "detalle": detalle,
            "monto": monto
        })
        
    cursor.execute("SELECT id, concepto, monto FROM gastos_fijos WHERE mes_ano = ?", (mes_ano,))
    gastos_items = []
    for g_id, concepto, monto in cursor.fetchall():
        gastos_items.append({
            "id": g_id,
            "concepto": concepto,
            "monto": monto
        })
        
    conn.close()
    
    # Retornar todas las estadísticas de negocio
    return jsonify({
        "inversion_total": inversion_total,
        "total_amortizado": total_amortizado,
        "saldo_pendiente": saldo_pendiente,
        "porcentaje_retorno": round(((inversion_total - saldo_pendiente) / inversion_total * 100) if inversion_total > 0 else 0.0, 1),
        "caja_mensual": caja_mensual,
        "gastos_fijos": gastos_fijos,
        "insumos": insumos_list,
        "alertas": alertas_list,
        "turnos_recientes": turnos_list,
        "inversion_items": inversion_items,
        "gastos_items": gastos_items
    })

@app.route('/api/barberos')
def get_barberos():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, comision_base FROM barberos")
    barberos = [{"id": r[0], "nombre": r[1], "comision_base": r[2]} for r in cursor.fetchall()]
    conn.close()
    return jsonify(barberos)

@app.route('/api/insumos')
def get_insumos():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre FROM insumos")
    insumos = [{"id": r[0], "nombre": r[1]} for r in cursor.fetchall()]
    conn.close()
    return jsonify(insumos)

@app.route('/api/turnos')
def get_turnos():
    barbero_id = request.args.get("barbero_id")
    conn = get_connection()
    cursor = conn.cursor()
    
    if barbero_id:
        cursor.execute("""
        SELECT t.id, t.cliente_nombre, t.cliente_telefono, t.fecha_hora, t.estado, b.nombre 
        FROM turnos t 
        JOIN barberos b ON t.barbero_id = b.id
        WHERE t.barbero_id = ?
        ORDER BY t.fecha_hora DESC
        """, (barbero_id,))
    else:
        cursor.execute("""
        SELECT t.id, t.cliente_nombre, t.cliente_telefono, t.fecha_hora, t.estado, b.nombre 
        FROM turnos t 
        JOIN barberos b ON t.barbero_id = b.id
        ORDER BY t.fecha_hora DESC
        """)
        
    turnos = []
    for t_id, cli_n, cli_tel, fh, est, bar_n in cursor.fetchall():
        turnos.append({
            "id": t_id,
            "cliente_nombre": cli_n,
            "cliente_telefono": cli_tel,
            "fecha_hora": fh,
            "estado": est,
            "barbero_nombre": bar_n
        })
        
    conn.close()
    return jsonify(turnos)

@app.route('/api/chat', methods=['POST'])
def process_chat():
    """
    Simulación del chatbot de reservas de WhatsApp
    """
    data = request.get_json() or {}
    name = data.get("name", "Cliente Simulado")
    phone = data.get("phone", "1100000000")
    message = data.get("message", "")
    
    if not message:
        return jsonify({"error": "Mensaje vacío"}), 400
        
    res = booking_agent.process_message(name, phone, message)
    return jsonify(res)

@app.route('/api/servicio', methods=['POST'])
def register_service():
    """
    Registro manual de un servicio por parte de un barbero
    """
    data = request.get_json() or {}
    barbero_id = data.get("barbero_id")
    servicio_nombre = data.get("servicio_nombre")
    monto_cobrado = float(data.get("monto_cobrado", 0))
    metodo_pago = data.get("metodo_pago", "Efectivo")
    insumo_id = data.get("insumo_id")
    ml_consumidos = float(data.get("ml_consumidos", 0))
    
    if not barbero_id or not servicio_nombre or monto_cobrado <= 0:
        return jsonify({"error": "Datos inválidos"}), 400
        
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Insertar servicio en la BD
    cursor.execute("""
    INSERT INTO servicios_realizados (turno_id, barbero_id, servicio_nombre, monto_cobrado, metodo_pago, ml_consumidos, insumo_id, fecha)
    VALUES (NULL, ?, ?, ?, ?, ?, ?, ?)
    """, (barbero_id, servicio_nombre, monto_cobrado, metodo_pago, ml_consumidos, insumo_id, fecha_hoy))
    conn.commit()
    conn.close()
    
    alerta_insumo = None
    # Restar del stock de insumo si aplica
    if insumo_id and ml_consumidos > 0:
        res_insumo = supply_agent.record_service_supplies(insumo_id, ml_consumidos)
        if res_insumo and res_insumo.get("alerta_bajo_stock"):
            alerta_insumo = res_insumo["alerta_mensaje"]
            
    return jsonify({
        "status": "success",
        "message": "Servicio registrado exitosamente.",
        "alerta_insumo": alerta_insumo
    })

@app.route('/api/gasto', methods=['POST'])
def register_expense():
    """
    Registro manual de un gasto fijo mensual
    """
    data = request.get_json() or {}
    concepto = data.get("concepto")
    monto = float(data.get("monto", 0))
    mes_ano = data.get("mes_ano", datetime.now().strftime("%Y-%m"))
    
    if not concepto or monto <= 0:
        return jsonify({"error": "Concepto o monto inválidos"}), 400
        
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO gastos_fijos (concepto, monto, mes_ano) VALUES (?, ?, ?)", (concepto, monto, mes_ano))
    conn.commit()
    conn.close()
    
    return jsonify({"status": "success", "message": "Gasto registrado exitosamente."})

@app.route('/api/inversion', methods=['POST'])
def register_inversion():
    """
    Registro manual de un item de la inversión inicial
    """
    data = request.get_json() or {}
    rubro = data.get("rubro")
    detalle = data.get("detalle")
    monto = float(data.get("monto", 0))
    
    if not rubro or not detalle or monto <= 0:
        return jsonify({"error": "Datos inválidos"}), 400
        
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO inversion_inicial (rubro, detalle, monto_pesos) VALUES (?, ?, ?)", (rubro, detalle, monto))
    conn.commit()
    conn.close()
    
    return jsonify({"status": "success", "message": "Inversión inicial registrada exitosamente."})

@app.route('/api/cierre', methods=['POST'])
def process_closure():
    """
    Cierre mensual y aplicación de comisiones y amortización
    """
    data = request.get_json() or {}
    mes_ano = data.get("mes_ano", "2026-06")
    
    report = finance_agent.run_monthly_closure(mes_ano)
    return jsonify(report)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    
    if not username or not password:
        return jsonify({"status": "error", "message": "Faltan credenciales"}), 400
        
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, role, barbero_id FROM usuarios WHERE username = ? AND password = ?", (username, password))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return jsonify({
            "status": "success",
            "username": username,
            "role": row[1],
            "barbero_id": row[2]
        })
    else:
        return jsonify({"status": "error", "message": "Usuario o contraseña incorrectos"}), 401

@app.route('/api/inversion/<int:item_id>', methods=['DELETE'])
def delete_inversion(item_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inversion_inicial WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Item de inversión eliminado."})

@app.route('/api/inversion/<int:item_id>', methods=['PUT'])
def update_inversion(item_id):
    data = request.get_json() or {}
    rubro = data.get("rubro")
    detalle = data.get("detalle")
    monto = float(data.get("monto", 0))
    
    if not rubro or not detalle or monto <= 0:
        return jsonify({"error": "Datos inválidos"}), 400
        
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE inversion_inicial SET rubro = ?, detalle = ?, monto_pesos = ? WHERE id = ?", (rubro, detalle, monto, item_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Item de inversión actualizado."})

@app.route('/api/gasto/<int:gasto_id>', methods=['DELETE'])
def delete_expense(gasto_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM gastos_fijos WHERE id = ?", (gasto_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Gasto eliminado."})

@app.route('/api/gasto/<int:gasto_id>', methods=['PUT'])
def update_expense(gasto_id):
    data = request.get_json() or {}
    concepto = data.get("concepto")
    monto = float(data.get("monto", 0))
    
    if not concepto or monto <= 0:
        return jsonify({"error": "Datos inválidos"}), 400
        
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE gastos_fijos SET concepto = ?, monto = ? WHERE id = ?", (concepto, monto, gasto_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Gasto actualizado."})

if __name__ == '__main__':
    # Crear carpetas estáticas si no existen
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    app.run(debug=True, port=5000)
