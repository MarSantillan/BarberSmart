from flask import Flask, request, jsonify, render_template
import sqlite3
from datetime import datetime
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
    cursor.execute("SELECT SUM(monto_cobrado) FROM servicios_realizados WHERE strftime('%Y-%m', fecha) = ? AND aprobado = 1", (mes_ano,))
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
        
    cursor.execute("""
    SELECT s.id, s.servicio_nombre, s.monto_cobrado, s.metodo_pago, s.ml_consumidos, s.insumo_id, s.fecha, b.nombre 
    FROM servicios_realizados s 
    JOIN barberos b ON s.barbero_id = b.id 
    WHERE s.aprobado = 0
    """)
    servicios_pendientes = []
    for s_id, s_nom, s_monto, s_pago, s_ml, s_ins_id, s_fecha, b_nom in cursor.fetchall():
        servicios_pendientes.append({
            "id": s_id,
            "servicio_nombre": s_nom,
            "monto_cobrado": s_monto,
            "metodo_pago": s_pago,
            "ml_consumidos": s_ml,
            "insumo_id": s_ins_id,
            "fecha": s_fecha,
            "barbero_nombre": b_nom
        })
        
    cursor.execute("""
    SELECT s.id, s.servicio_nombre, s.monto_cobrado, s.metodo_pago, s.ml_consumidos, s.insumo_id, s.fecha, b.nombre 
    FROM servicios_realizados s 
    JOIN barberos b ON s.barbero_id = b.id 
    WHERE s.aprobado = 1 AND strftime('%Y-%m', s.fecha) = ?
    """, (mes_ano,))
    servicios_aprobados = []
    for s_id, s_nom, s_monto, s_pago, s_ml, s_ins_id, s_fecha, b_nom in cursor.fetchall():
        servicios_aprobados.append({
            "id": s_id,
            "servicio_nombre": s_nom,
            "monto_cobrado": s_monto,
            "metodo_pago": s_pago,
            "ml_consumidos": s_ml,
            "insumo_id": s_ins_id,
            "fecha": s_fecha,
            "barbero_nombre": b_nom
        })
        
    conn.close()
    
    # Obtener liquidación estimada en tiempo real
    status_estimado = finance_agent.calculate_monthly_status("2026-06")
    
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
        "gastos_items": gastos_items,
        "servicios_pendientes": servicios_pendientes,
        "servicios_aprobados": servicios_aprobados,
        "status_estimado": status_estimado
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
    cursor.execute("SELECT id, nombre, ml_totales, ml_actuales FROM insumos")
    insumos = [{"id": r[0], "nombre": r[1], "ml_totales": r[2], "ml_actuales": r[3]} for r in cursor.fetchall()]
    conn.close()
    return jsonify(insumos)

@app.route('/api/insumo/reponer', methods=['POST'])
def replenish_supply_route():
    data = request.get_json() or {}
    insumo_id = data.get("insumo_id")
    unidades = data.get("unidades")
    ml_por_unidad = data.get("ml_por_unidad")
    precio_total = data.get("precio_total")
    
    if not insumo_id or not unidades or not ml_por_unidad or not precio_total:
        return jsonify({"error": "Faltan datos requeridos para la reposición."}), 400
        
    try:
        insumo_id = int(insumo_id)
        unidades = int(unidades)
        ml_por_unidad = float(ml_por_unidad)
        precio_total = float(precio_total)
    except ValueError:
        return jsonify({"error": "Tipos de datos inválidos."}), 400
        
    res = supply_agent.replenish_supply(insumo_id, unidades, ml_por_unidad, precio_total)
    if "error" in res:
        return jsonify(res), 400
        
    return jsonify(res)


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

@app.route('/api/whatsapp/webhook', methods=['POST'])
def whatsapp_webhook():
    """
    Webhook para integrar el bot de reservas con Twilio WhatsApp API.
    Recibe datos de formulario (application/x-www-form-urlencoded) y responde en formato TwiML (XML).
    """
    import html
    
    # Extraer variables de la petición de Twilio
    message = request.form.get('Body', '').strip()
    from_number = request.form.get('From', '')
    profile_name = request.form.get('ProfileName', 'Cliente')

    if not message:
        return ("", 200, {'Content-Type': 'text/xml'})

    # Formatear teléfono (quitar prefijo 'whatsapp:')
    client_phone = from_number.replace('whatsapp:', '').strip()
    client_name = profile_name

    # Procesar con el agente ReAct de reservas
    res = booking_agent.process_message(client_name, client_phone, message)
    response_text = res.get("response", "")

    # Escapar caracteres para evitar XML inválido
    escaped_response = html.escape(response_text)

    # Formar la respuesta TwiML nativa
    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{escaped_response}</Message>
</Response>"""

    return (twiml_response, 200, {'Content-Type': 'text/xml'})


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

@app.route('/api/servicio/aprobar/<int:srv_id>', methods=['POST'])
def approve_service(srv_id):
    """
    Aprueba un servicio realizado por un barbero y opcionalmente permite corregir el monto cobrado.
    """
    data = request.get_json() or {}
    monto_cobrado = data.get("monto_cobrado")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    if monto_cobrado is not None:
        cursor.execute("UPDATE servicios_realizados SET aprobado = 1, monto_cobrado = ? WHERE id = ?", (float(monto_cobrado), srv_id))
    else:
        cursor.execute("UPDATE servicios_realizados SET aprobado = 1 WHERE id = ?", (srv_id,))
        
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Servicio auditado y aprobado."})

@app.route('/api/servicio/rechazar/<int:srv_id>', methods=['POST'])
def reject_service(srv_id):
    """
    Rechaza (elimina) un servicio realizado por un barbero si fue cargado incorrectamente.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM servicios_realizados WHERE id = ?", (srv_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Servicio rechazado y eliminado."})

@app.route('/api/servicio/<int:srv_id>', methods=['PUT'])
def update_service(srv_id):
    """
    Modifica el monto cobrado de un servicio auditado/registrado.
    """
    data = request.get_json() or {}
    monto_cobrado = data.get("monto_cobrado")
    
    if monto_cobrado is None or float(monto_cobrado) <= 0:
        return jsonify({"error": "Monto cobrado inválido."}), 400
        
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE servicios_realizados SET monto_cobrado = ? WHERE id = ?", (float(monto_cobrado), srv_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Servicio actualizado correctamente."})

@app.route('/api/barbero/servicios')
def get_barbero_servicios():
    """
    Retorna la lista de servicios cargados por un barbero en el mes, EXCLUYENDO montos financieros.
    """
    barbero_id = request.args.get("barbero_id")
    if not barbero_id:
        return jsonify({"error": "Falta barbero_id"}), 400
        
    conn = get_connection()
    cursor = conn.cursor()
    mes_ano = "2026-06"
    cursor.execute("""
    SELECT id, servicio_nombre, metodo_pago, ml_consumidos, insumo_id, fecha, aprobado
    FROM servicios_realizados
    WHERE barbero_id = ? AND strftime('%Y-%m', fecha) = ?
    ORDER BY fecha DESC, id DESC
    """, (barbero_id, mes_ano))
    
    servicios = []
    for s_id, s_nom, s_pago, s_ml, s_ins_id, s_fecha, aprobado in cursor.fetchall():
        servicios.append({
            "id": s_id,
            "servicio_nombre": s_nom,
            "metodo_pago": s_pago,
            "ml_consumidos": s_ml,
            "insumo_id": s_ins_id,
            "fecha": s_fecha,
            "aprobado": aprobado
        })
    conn.close()
    return jsonify(servicios)

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

@app.route('/api/turno/<int:turno_id>', methods=['DELETE'])
def delete_turno(turno_id):
    conn = get_connection()
    cursor = conn.cursor()
    # Desvincular de servicios_realizados para evitar violaciones de clave foránea en Postgres
    cursor.execute("UPDATE servicios_realizados SET turno_id = NULL WHERE turno_id = ?", (turno_id,))
    cursor.execute("DELETE FROM turnos WHERE id = ?", (turno_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Turno eliminado de la agenda."})

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
