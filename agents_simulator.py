import sqlite3
from datetime import datetime, timedelta
import re
from database import get_connection

# ==========================================
# 1. BOOKING AGENT (Gestión de Turnos)
# ==========================================

class BookingAgent:
    def __init__(self):
        pass

    def parse_date(self, text):
        text = text.lower()
        now = datetime.now()
        
        # Próximos días de la semana
        days = {
            "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2,
            "jueves": 3, "viernes": 4, "sabado": 5, "sábado": 5,
            "domingo": 6
        }
        for day_name, day_num in days.items():
            if day_name in text:
                days_ahead = day_num - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                target_date = now + timedelta(days=days_ahead)
                return target_date.strftime("%Y-%m-%d")
                
        # Formato YYYY-MM-DD
        match_date_long = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        if match_date_long:
            return match_date_long.group(1)
            
        # Formato DD/MM o DD-MM
        match_date_short = re.search(r"(\d{1,2})[/-](\d{1,2})", text)
        if match_date_short:
            day = int(match_date_short.group(1))
            month = int(match_date_short.group(2))
            return f"{now.year:04d}-{month:02d}-{day:02d}"
            
        return None

    def parse_time(self, text):
        text = text.lower()
        
        # Formato HH:MM
        match_time = re.search(r"(\d{1,2}):(\d{2})", text)
        if match_time:
            hour = int(match_time.group(1))
            minute = int(match_time.group(2))
            return f"{hour:02d}:{minute:02d}"
            
        # Formato HH hs o a las HH
        match_hour = re.search(r"(?:a las|a las\s|\s)(\d{1,2})\s*(?:hs|horas|hora|am|pm)?", text)
        if match_hour:
            hour = int(match_hour.group(1))
            if 8 <= hour <= 21:
                return f"{hour:02d}:00"
                
        # Buscar un número suelto entre 8 y 20
        match_number = re.search(r"\b(8|9|10|11|12|13|14|15|16|17|18|19|20)\b", text)
        if match_number:
            return f"{int(match_number.group(1)):02d}:00"
            
        return None

    def parse_servicio(self, text):
        text = text.lower()
        if "corte de pelo" in text or "corte de cabello" in text or "corte" in text:
            if "barba" in text:
                return "Corte y Barba"
            return "Corte de pelo"
        elif "corte y barba" in text or "barba" in text or "afeitado" in text:
            return "Corte y Barba"
        elif "tintura" in text or "teñir" in text or "color" in text:
            return "Tintura"
        elif "champu" in text or "champú" in text or "lavado" in text:
            return "Champú"
        elif "locion" in text or "loción" in text:
            return "Loción Post Afeitado"
        return None

    def get_chat_state(self, phone):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT state, cliente_nombre, barbero_id, servicio_nombre, fecha, hora FROM chat_states WHERE phone = ?", (phone,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "state": row[0],
                "cliente_nombre": row[1],
                "barbero_id": row[2],
                "servicio_nombre": row[3],
                "fecha": row[4],
                "hora": row[5]
            }
        return None

    def save_chat_state(self, phone, state_dict):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM chat_states WHERE phone = ?", (phone,))
        exists = cursor.fetchone()[0] > 0
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if exists:
            cursor.execute("""
            UPDATE chat_states SET 
                state = ?, cliente_nombre = ?, barbero_id = ?, 
                servicio_nombre = ?, fecha = ?, hora = ?, updated_at = ?
            WHERE phone = ?
            """, (
                state_dict["state"], state_dict.get("cliente_nombre"), state_dict.get("barbero_id"),
                state_dict.get("servicio_nombre"), state_dict.get("fecha"), state_dict.get("hora"),
                now_str, phone
            ))
        else:
            cursor.execute("""
            INSERT INTO chat_states (phone, state, cliente_nombre, barbero_id, servicio_nombre, fecha, hora, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                phone, state_dict["state"], state_dict.get("cliente_nombre"), state_dict.get("barbero_id"),
                state_dict.get("servicio_nombre"), state_dict.get("fecha"), state_dict.get("hora"),
                now_str
            ))
        conn.commit()
        conn.close()

    def delete_chat_state(self, phone):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_states WHERE phone = ?", (phone,))
        conn.commit()
        conn.close()

    def get_barbero_details(self, barbero_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT nombre, telefono FROM barberos WHERE id = ?", (barbero_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"nombre": row[0], "telefono": row[1]}
        return {"nombre": "Desconocido", "telefono": ""}

    def process_message(self, client_name, client_phone, message):
        message_lower = message.lower().strip()
        
        # 1. Chequear Cancelación
        if "cancelar" in message_lower or "anular" in message_lower:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            SELECT t.id, t.fecha_hora, b.nombre, b.id 
            FROM turnos t 
            JOIN barberos b ON t.barbero_id = b.id 
            WHERE t.cliente_telefono = ? AND t.estado IN ('Confirmado', 'Pendiente') 
            ORDER BY t.fecha_hora DESC LIMIT 1
            """, (client_phone,))
            row = cursor.fetchone()
            
            if row:
                turno_id, fecha_hora, barbero_nombre, barbero_id = row
                cursor.execute("UPDATE turnos SET estado = 'Cancelado' WHERE id = ?", (turno_id,))
                conn.commit()
                conn.close()
                
                # Eliminar estado del chat
                self.delete_chat_state(client_phone)
                
                # Notificar al barbero
                self.notify_barber_cancellation(barbero_id, client_name, fecha_hora)
                
                return {
                    "status": "cancelled",
                    "response": f"Tu turno con {barbero_nombre} para el día {fecha_hora} hs ha sido cancelado correctamente. Esperamos verte pronto!"
                }
            else:
                conn.close()
                return {
                    "status": "error",
                    "response": "No encontramos ningún turno activo o pendiente asociado a tu número de teléfono para cancelar."
                }
                
        # 2. Flujo de reserva
        state = self.get_chat_state(client_phone)
        if not state:
            state = {
                "state": "AWAITING_INFO",
                "cliente_nombre": client_name,
                "barbero_id": None,
                "servicio_nombre": None,
                "fecha": None,
                "hora": None
            }
            
        # Parsear variables del mensaje del usuario
        new_barbero_name = None
        if "lucas" in message_lower:
            new_barbero_name = "Lucas"
        elif "martin" in message_lower or "martín" in message_lower:
            new_barbero_name = "Martín"
        elif "cualquiera" in message_lower or "cualquier" in message_lower:
            new_barbero_name = "Cualquiera"
            
        new_service = self.parse_servicio(message_lower)
        new_date = self.parse_date(message_lower)
        new_time = self.parse_time(message_lower)
        
        # Lógica en base al estado de la conversación
        if state["state"] == "AWAITING_CONFIRMATION":
            # Si el usuario responde afirmativamente
            if any(confirm_word in message_lower for confirm_word in ["si", "sí", "confirmar", "confirmo", "ok", "dale", "correcto", "de una"]):
                barbero_id = state["barbero_id"]
                servicio_nombre = state["servicio_nombre"]
                fecha = state["fecha"]
                hora = state["hora"]
                fecha_hora_solicitada = f"{fecha} {hora}"
                
                conn = get_connection()
                cursor = conn.cursor()
                
                # Doble chequeo de disponibilidad (por si otro reservó en el medio)
                cursor.execute("""
                SELECT COUNT(*) FROM turnos 
                WHERE barbero_id = ? AND fecha_hora = ? AND estado != 'Cancelado'
                """, (barbero_id, fecha_hora_solicitada))
                ocupado = cursor.fetchone()[0] > 0
                
                if not ocupado:
                    # Reservar turno
                    cursor.execute("""
                    INSERT INTO turnos (cliente_nombre, cliente_telefono, barbero_id, fecha_hora, estado)
                    VALUES (?, ?, ?, ?, 'Confirmado')
                    """, (client_name, client_phone, barbero_id, fecha_hora_solicitada))
                    conn.commit()
                    conn.close()
                    
                    # Eliminar estado del chat
                    self.delete_chat_state(client_phone)
                    
                    # Notificar al barbero
                    self.notify_barber(barbero_id, client_name, fecha_hora_solicitada, servicio_nombre)
                    
                    barbero_det = self.get_barbero_details(barbero_id)
                    return {
                        "status": "confirmed",
                        "response": f"¡Turno confirmado para {client_name}! Corte programado para el día {fecha} a las {hora} hs con el barbero {barbero_det['nombre']}."
                    }
                else:
                    # Ocupado en el último segundo. Proponer alternativas.
                    conn.close()
                    state["state"] = "AWAITING_INFO"
                    # Resetear fecha y hora para que el bot las vuelva a pedir o proponer
                    state["fecha"] = None
                    state["hora"] = None
                    self.save_chat_state(client_phone, state)
                    
                    # Buscar alternativas
                    return self.generate_alternatives_response(client_phone, state, fecha_hora_solicitada)
            
            # Si el usuario responde negativamente o quiere cambiar algo
            elif any(neg_word in message_lower for neg_word in ["no", "cambiar", "cancelar", "modificar", "editar"]):
                # Si en el mensaje especificó qué cambiar (ej. "con Martin" o "a las 17")
                has_updates = False
                if new_barbero_name:
                    has_updates = True
                    if new_barbero_name == "Cualquiera":
                        state["barbero_id"] = self.assign_random_barber()
                    else:
                        state["barbero_id"] = self.get_barber_id_by_name(new_barbero_name)
                if new_service:
                    has_updates = True
                    state["servicio_nombre"] = new_service
                if new_date:
                    has_updates = True
                    state["fecha"] = new_date
                if new_time:
                    has_updates = True
                    state["hora"] = new_time
                    
                if has_updates:
                    # Chequear disponibilidad del nuevo horario si se cambiaron fecha/hora
                    fecha_hora_solicitada = f"{state['fecha']} {state['hora']}"
                    if state["fecha"] and state["hora"] and state["barbero_id"]:
                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute("""
                        SELECT COUNT(*) FROM turnos 
                        WHERE barbero_id = ? AND fecha_hora = ? AND estado != 'Cancelado'
                        """, (state["barbero_id"], fecha_hora_solicitada))
                        ocupado = cursor.fetchone()[0] > 0
                        conn.close()
                        if ocupado:
                            return self.generate_alternatives_response(client_phone, state, fecha_hora_solicitada)
                            
                    state["state"] = "AWAITING_CONFIRMATION"
                    self.save_chat_state(client_phone, state)
                    barbero_det = self.get_barbero_details(state["barbero_id"])
                    return {
                        "status": "awaiting_confirmation",
                        "response": f"Entendido, he actualizado los datos. Por favor confirma:\n- Barbero: {barbero_det['nombre']}\n- Servicio: {state['servicio_nombre']}\n- Fecha y Hora: {state['fecha']} a las {state['hora']} hs.\n\n¿Confirmas ahora? (SÍ/NO)"
                    }
                else:
                    state["state"] = "AWAITING_INFO"
                    # Resetear para volver a preguntar
                    self.save_chat_state(client_phone, state)
                    return {
                        "status": "awaiting_info",
                        "response": "Está bien, no confirmamos los datos. ¿Qué te gustaría modificar? Puedes indicarme el nuevo barbero, servicio o fecha/hora."
                    }
            else:
                # Si escribió algo no concluyente, tratar de interpretarlo como nuevas modificaciones
                has_updates = False
                if new_barbero_name:
                    has_updates = True
                    if new_barbero_name == "Cualquiera":
                        state["barbero_id"] = self.assign_random_barber()
                    else:
                        state["barbero_id"] = self.get_barber_id_by_name(new_barbero_name)
                if new_service:
                    has_updates = True
                    state["servicio_nombre"] = new_service
                if new_date:
                    has_updates = True
                    state["fecha"] = new_date
                if new_time:
                    has_updates = True
                    state["hora"] = new_time
                    
                if has_updates:
                    state["state"] = "AWAITING_CONFIRMATION"
                    self.save_chat_state(client_phone, state)
                    barbero_det = self.get_barbero_details(state["barbero_id"])
                    return {
                        "status": "awaiting_confirmation",
                        "response": f"He actualizado los detalles. Por favor confirma si es correcto:\n- Barbero: {barbero_det['nombre']}\n- Servicio: {state['servicio_nombre']}\n- Fecha y Hora: {state['fecha']} a las {state['hora']} hs.\n\n¿Confirmas ahora? (SÍ/NO)"
                    }
                else:
                    return {
                        "status": "awaiting_confirmation",
                        "response": "Por favor, responde SÍ para confirmar el turno con los datos mencionados, o NO si deseas modificarlos."
                    }

        # Estado AWAITING_INFO o Estado nuevo:
        # Actualizar los campos que el usuario mencionó
        if new_barbero_name:
            if new_barbero_name == "Cualquiera":
                state["barbero_id"] = self.assign_random_barber()
            else:
                state["barbero_id"] = self.get_barber_id_by_name(new_barbero_name)
        if new_service:
            state["servicio_nombre"] = new_service
        if new_date:
            state["fecha"] = new_date
        if new_time:
            state["hora"] = new_time

        # Verificar qué datos faltan y preguntar específicamente
        if not state["barbero_id"]:
            self.save_chat_state(client_phone, state)
            return {
                "status": "awaiting_info",
                "response": "¡Hola! Bienvenido a la Barbería. ¿Con qué barbero te gustaría atenderte? (Tenemos a Lucas y Martín, o puedes decir 'cualquiera')"
            }
            
        if not state["servicio_nombre"]:
            self.save_chat_state(client_phone, state)
            return {
                "status": "awaiting_info",
                "response": "¿Qué servicio te gustaría realizarte? (Corte de pelo, Corte y Barba, Tintura, Champú, Loción Post Afeitado)"
            }
            
        if not state["fecha"] or not state["hora"]:
            self.save_chat_state(client_phone, state)
            return {
                "status": "awaiting_info",
                "response": "¿Para qué día y horario te gustaría reservar? (Por ejemplo: 'el sábado a las 15 hs' o '2026-06-27 a las 16 hs')"
            }

        # Si tenemos todo, verificar disponibilidad
        fecha_hora_solicitada = f"{state['fecha']} {state['hora']}"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT COUNT(*) FROM turnos 
        WHERE barbero_id = ? AND fecha_hora = ? AND estado != 'Cancelado'
        """, (state["barbero_id"], fecha_hora_solicitada))
        ocupado = cursor.fetchone()[0] > 0
        conn.close()
        
        if ocupado:
            # Reservar espacio ocupado. Proponer alternativas
            return self.generate_alternatives_response(client_phone, state, fecha_hora_solicitada)
            
        # Todo listo y disponible, pasar a confirmación
        state["state"] = "AWAITING_CONFIRMATION"
        self.save_chat_state(client_phone, state)
        
        barbero_det = self.get_barbero_details(state["barbero_id"])
        return {
            "status": "awaiting_confirmation",
            "response": f"¡Perfecto! Tengo todos los datos listos para agendar:\n- Barbero: {barbero_det['nombre']}\n- Servicio: {state['servicio_nombre']}\n- Fecha y Hora: {state['fecha']} a las {state['hora']} hs.\n\n¿Confirmas estos datos? Responde SÍ para confirmar o NO si quieres realizar algún cambio."
        }

    def assign_random_barber(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM barberos ORDER BY RANDOM() LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 1

    def get_barber_id_by_name(self, name):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM barberos WHERE nombre = ?", (name,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 1

    def generate_alternatives_response(self, client_phone, state, fecha_hora_solicitada):
        barbero_id = state["barbero_id"]
        date_str = state["fecha"]
        time_str = state["hora"]
        barbero_det = self.get_barbero_details(barbero_id)
        barbero_name = barbero_det["nombre"]
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Buscar horarios libres del barbero en la misma fecha (ej. 10:00, 11:00, 14:00, 17:00)
        horarios_propuestos = ["10:00", "11:00", "14:00", "17:00"]
        libres_mismo_barbero = []
        
        for h in horarios_propuestos:
            test_fh = f"{date_str} {h}"
            cursor.execute("""
            SELECT COUNT(*) FROM turnos 
            WHERE barbero_id = ? AND fecha_hora = ? AND estado != 'Cancelado'
            """, (barbero_id, test_fh))
            if cursor.fetchone()[0] == 0:
                libres_mismo_barbero.append(h)
        
        # Buscar si el otro barbero está libre a la misma hora
        cursor.execute("SELECT id, nombre FROM barberos WHERE id != ?", (barbero_id,))
        otro_barbero = cursor.fetchone()
        otro_libre = False
        
        if otro_barbero:
            cursor.execute("""
            SELECT COUNT(*) FROM turnos 
            WHERE barbero_id = ? AND fecha_hora = ? AND estado != 'Cancelado'
            """, (otro_barbero[0], fecha_hora_solicitada))
            if cursor.fetchone()[0] == 0:
                otro_libre = True
                
        conn.close()
        
        # Modificar el estado actual indicando que necesitamos nueva fecha/hora
        state["fecha"] = None
        state["hora"] = None
        state["state"] = "AWAITING_INFO"
        self.save_chat_state(client_phone, state)
        
        # Formular propuesta alternativa
        alternativas_msg = f"Disculpas, {barbero_name} ya se encuentra ocupado a las {time_str} hs el día {date_str}.\n"
        if otro_libre:
            alternativas_msg += f"• ¿Te gustaría agendar a esa misma hora ({time_str} hs) con el barbero {otro_barbero[1]}?\n"
        if libres_mismo_barbero:
            alternativas_msg += f"• O puedes elegir a {barbero_name} ese mismo día a las: {', '.join(libres_mismo_barbero)} hs.\n"
        else:
            alternativas_msg += f"• O dinos otra fecha u hora conveniente."
            
        alternativas_msg += "\n¿Cuál prefieres? (o puedes decir otro día y horario)."
        
        return {
            "status": "suggested_alternatives",
            "response": alternativas_msg
        }

    def notify_barber(self, barbero_id, cliente_nombre, fecha_hora, servicio_nombre):
        details = self.get_barbero_details(barbero_id)
        barbero_nombre = details["nombre"]
        barbero_telefono = details["telefono"]
        
        if not barbero_telefono:
            print(f"[NOTIFICACIÓN] No se pudo notificar a {barbero_nombre}: No tiene teléfono registrado.")
            return
            
        mensaje = f"Hola {barbero_nombre}, tienes un nuevo turno confirmado.\nCliente: {cliente_nombre}\nServicio: {servicio_nombre}\nFecha y Hora: {fecha_hora} hs."
        self._send_whatsapp(barbero_telefono, mensaje)

    def notify_barber_cancellation(self, barbero_id, cliente_nombre, fecha_hora):
        details = self.get_barbero_details(barbero_id)
        barbero_nombre = details["nombre"]
        barbero_telefono = details["telefono"]
        
        if not barbero_telefono:
            print(f"[NOTIFICACIÓN] No se pudo notificar a {barbero_nombre}: No tiene teléfono registrado.")
            return
            
        mensaje = f"Hola {barbero_nombre}, el turno de {cliente_nombre} para el día {fecha_hora} hs ha sido CANCELADO por el cliente."
        self._send_whatsapp(barbero_telefono, mensaje)

    def _send_whatsapp(self, to_number, body):
        import os
        import urllib.request
        import urllib.parse
        import base64
        
        sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        from_number = os.environ.get("TWILIO_NUMBER", "whatsapp:+14155238886")
        
        if not to_number.startswith("whatsapp:"):
            clean_num = "".join(c for c in to_number if c.isdigit() or c == "+")
            if not clean_num.startswith("+"):
                if len(clean_num) == 10:
                    clean_num = f"+549{clean_num}"
                else:
                    clean_num = f"+{clean_num}"
            to_number = f"whatsapp:{clean_num}"
            
        print(f"\n=================== TWILIO OUTBOX ===================")
        print(f"Para: {to_number}")
        print(f"Contenido:\n{body}")
        print(f"=====================================================\n")
        
        if not sid or not auth_token:
            print("[TWILIO] Credenciales ausentes. Simulación local exitosa.")
            return True
            
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        data = urllib.parse.urlencode({
            "From": from_number,
            "To": to_number,
            "Body": body
        }).encode("utf-8")
        
        req = urllib.request.Request(url, data=data, method="POST")
        auth_str = f"{sid}:{auth_token}"
        auth_b64 = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        req.add_header("Authorization", f"Basic {auth_b64}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        
        try:
            with urllib.request.urlopen(req) as response:
                print(f"[TWILIO SUCCESS] Mensaje real enviado a {to_number}.")
                return True
        except Exception as e:
            print(f"[TWILIO ERROR] No se pudo enviar el mensaje real: {e}")
            return False


# ==========================================
# 2. FINANCE & AMORTIZATION AGENT (Liquidación)
# ==========================================

class FinanceAgent:
    def __init__(self):
        pass

    def calculate_monthly_status(self, mes_ano):
        """
        Calcula la liquidación financiera del mes y estima las comisiones dinámicas y la amortización,
        sin persistir cambios en la tabla de amortizaciones.
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        # 1. Obtener los gastos fijos del mes
        cursor.execute("SELECT SUM(monto) FROM gastos_fijos WHERE mes_ano = ?", (mes_ano,))
        row = cursor.fetchone()
        gastos_fijos = row[0] if row[0] else 0.0
        
        # 2. Obtener el costo de los insumos comprados en el mes
        cursor.execute("SELECT SUM(precio_compra) FROM insumos WHERE strftime('%Y-%m', fecha_compra) = ?", (mes_ano,))
        row = cursor.fetchone()
        gastos_insumos = row[0] if row[0] else 0.0
        
        total_gastos_local = gastos_fijos + gastos_insumos
        
        # 3. Obtener el bruto generado por cada barbero (solo APROBADOS)
        cursor.execute("""
        SELECT barbero_id, SUM(monto_cobrado) 
        FROM servicios_realizados 
        WHERE strftime('%Y-%m', fecha) = ? AND aprobado = 1
        GROUP BY barbero_id
        """, (mes_ano,))
        
        servicios_por_barbero = cursor.fetchall()
        total_bruto_generado = sum(s[1] for s in servicios_por_barbero)
        
        # 4. Evaluación de la Comisión Dinámica
        local_share_standard = total_bruto_generado * 0.50
        
        if total_bruto_generado == 0:
            comision_efectiva = 50.0
            contingencia_activa = False
        elif local_share_standard < total_gastos_local:
            comision_efectiva = 40.0
            contingencia_activa = True
        else:
            comision_efectiva = 50.0
            contingencia_activa = False
            
        # 5. Calcular liquidación para cada barbero
        reporte_barberos = []
        shop_share_total = 0.0
        barber_payout_total = 0.0
        
        for barbero_id, bruto in servicios_por_barbero:
            cursor.execute("SELECT nombre FROM barberos WHERE id = ?", (barbero_id,))
            b_nombre = cursor.fetchone()[0]
            
            payout = bruto * (comision_efectiva / 100.0)
            shop_cut = bruto * ((100.0 - comision_efectiva) / 100.0)
            
            # Obtener propinas digitales si las hubiera (solo aprobadas)
            cursor.execute("""
            SELECT SUM(propina_digital) FROM servicios_realizados 
            WHERE barbero_id = ? AND strftime('%Y-%m', fecha) = ? AND aprobado = 1
            """, (barbero_id, mes_ano))
            propinas = cursor.fetchone()[0]
            propinas = propinas if propinas else 0.0
            
            reporte_barberos.append({
                "barbero_id": barbero_id,
                "nombre": b_nombre,
                "bruto_generado": bruto,
                "comision_porcentaje": comision_efectiva,
                "payout_neto": payout,
                "propinas_digitales": propinas,
                "payout_total_con_propinas": payout + propinas
            })
            
            shop_share_total += shop_cut
            barber_payout_total += payout
            
        # 6. Calcular ganancia neta del dueño
        ganancia_neta_dueno = shop_share_total - total_gastos_local
        
        # 7. Amortización de la inversión inicial
        cursor.execute("SELECT SUM(monto_pesos) FROM inversion_inicial")
        inversion_total = cursor.fetchone()[0]
        inversion_total = inversion_total if inversion_total else 0.0
        
        # Obtener saldo pendiente previo
        cursor.execute("SELECT saldo_pendiente FROM amortizaciones ORDER BY id DESC LIMIT 1")
        prev_saldo_row = cursor.fetchone()
        if prev_saldo_row:
            saldo_pendiente_previo = prev_saldo_row[0]
        else:
            saldo_pendiente_previo = inversion_total
            
        monto_amortizado = 0.0
        nuevo_saldo = saldo_pendiente_previo
        
        if ganancia_neta_dueno > 0 and saldo_pendiente_previo > 0:
            monto_amortizado = min(ganancia_neta_dueno, saldo_pendiente_previo)
            nuevo_saldo = saldo_pendiente_previo - monto_amortizado
            
        conn.close()
        
        return {
            "mes_ano": mes_ano,
            "total_bruto_generado": total_bruto_generado,
            "gastos_fijos": gastos_fijos,
            "gastos_insumos": gastos_insumos,
            "total_gastos_local": total_gastos_local,
            "contingencia_comision_activa": contingencia_activa,
            "comision_applied": comision_efectiva,
            "comision_aplicada": comision_efectiva, # retrocompatibilidad
            "retencion_local_total": shop_share_total,
            "ganancia_neta_dueno_bruta": ganancia_neta_dueno,
            "monto_amortizado_este_mes": monto_amortizado,
            "ganancia_liquida_dueño": max(0.0, ganancia_neta_dueno - monto_amortizado),
            "inversion_total_inicial": inversion_total,
            "saldo_pendiente_inversion": nuevo_saldo,
            "retorno_porcentaje": round(((inversion_total - nuevo_saldo) / inversion_total * 100) if inversion_total > 0 else 0.0, 2),
            "reporte_barberos": reporte_barberos
        }

    def run_monthly_closure(self, mes_ano):
        """
        Calcula la liquidación financiera y guarda el registro de amortización si corresponde,
        previniendo duplicaciones para el mismo mes.
        """
        status = self.calculate_monthly_status(mes_ano)
        
        if status["monto_amortizado_este_mes"] > 0:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Verificar si ya existe amortización registrada para este mes
            cursor.execute("SELECT COUNT(*) FROM amortizaciones WHERE mes_ano = ?", (mes_ano,))
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                INSERT INTO amortizaciones (mes_ano, monto_amortizado, saldo_pendiente)
                VALUES (?, ?, ?)
                """, (mes_ano, status["monto_amortizado_este_mes"], status["saldo_pendiente_inversion"]))
                conn.commit()
                
            conn.close()
            
        return status


# ==========================================
# 3. SUPPLY AGENT (Consumo de Insumos)
# ==========================================

class SupplyAgent:
    def __init__(self):
        pass

    def replenish_supply(self, insumo_id, unidades, ml_por_unidad, precio_total):
        """
        Incrementa la cantidad de mililitros (tanto actual como total para conservar el ratio)
        y registra el gasto correspondiente de forma automática.
        """
        if not insumo_id or unidades <= 0 or ml_por_unidad <= 0 or precio_total <= 0:
            return {"error": "Datos inválidos"}
            
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT nombre FROM insumos WHERE id = ?", (insumo_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return {"error": "Insumo no encontrado"}
            
        nombre = row[0]
        ml_agregados = unidades * ml_por_unidad
        
        # Actualizar stock en BD (ml_actuales y ml_totales)
        cursor.execute("""
            UPDATE insumos 
            SET ml_actuales = ml_actuales + ?, ml_totales = ml_totales + ? 
            WHERE id = ?
        """, (ml_agregados, ml_agregados, insumo_id))
        
        # Registrar automáticamente el gasto fijo en gastos_fijos
        concepto = f"Reposición: {nombre} x{unidades}"
        mes_ano = datetime.now().strftime("%Y-%m")
        cursor.execute("""
            INSERT INTO gastos_fijos (concepto, monto, mes_ano) 
            VALUES (?, ?, ?)
        """, (concepto, precio_total, mes_ano))
        
        conn.commit()
        
        # Obtener estado actualizado
        cursor.execute("SELECT ml_actuales, ml_totales FROM insumos WHERE id = ?", (insumo_id,))
        ml_act, ml_tot = cursor.fetchone()
        conn.close()
        
        return {
            "status": "success",
            "nombre": nombre,
            "ml_agregados": ml_agregados,
            "ml_actuales": ml_act,
            "ml_totales": ml_tot,
            "monto_gasto": precio_total,
            "concepto": concepto
        }

    def record_service_supplies(self, insumo_id, ml_usados):
        """
        Resta la cantidad de mililitros utilizados del inventario.
        Lanza alertas si el nivel está bajo.
        """
        if not insumo_id or ml_usados <= 0:
            return None
            
        conn = get_connection()
        cursor = conn.cursor()
        
        # 1. Obtener estado del insumo
        cursor.execute("SELECT nombre, ml_totales, ml_actuales FROM insumos WHERE id = ?", (insumo_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return {"error": "Insumo no encontrado"}
            
        nombre, ml_totales, ml_actuales = row
        nuevo_ml = max(0.0, ml_actuales - ml_usados)
        
        # 2. Actualizar stock en BD
        cursor.execute("UPDATE insumos SET ml_actuales = ? WHERE id = ?", (nuevo_ml, insumo_id))
        conn.commit()
        conn.close()
        
        # 3. Evaluar alerta de bajo stock (menor a 15% de la capacidad total)
        umbral_alerta = ml_totales * 0.15
        alerta_activa = nuevo_ml < umbral_alerta
        
        return {
            "insumo_id": insumo_id,
            "nombre": nombre,
            "ml_anterior": ml_actuales,
            "ml_actual": nuevo_ml,
            "ml_consumidos": ml_usados,
            "alerta_bajo_stock": alerta_activa,
            "alerta_mensaje": f"¡ALERTA DE STOCK CRÍTICO! El producto '{nombre}' cuenta con {nuevo_ml:.1f} ml restantes (menos del 15%). Requiere reposición inmediata." if alerta_activa else None
        }
