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

    def parse_date_time(self, text):
        """
        Analiza texto conversacional simple para extraer fecha y hora del turno.
        Soporta formatos tipo: 'sabado a las 15', '2026-06-27 a las 16:30', etc.
        Para propósitos de simulación, asume el próximo sábado o una fecha específica.
        """
        text = text.lower()
        now = datetime.now()
        
        # Simular fecha del próximo sábado
        if "sabado" in text or "sábado" in text:
            days_ahead = 5 - now.weekday() # Sábado es 5
            if days_ahead <= 0: # Si ya es sábado o domingo
                days_ahead += 7
            target_date = now + timedelta(days=days_ahead)
            date_str = target_date.strftime("%Y-%m-%d")
        else:
            # Buscar fecha formato YYYY-MM-DD
            match_date = re.search(r"(\d{4}-\d{2}-\d{2})", text)
            if match_date:
                date_str = match_date.group(1)
            else:
                # Por defecto hoy
                date_str = now.strftime("%Y-%m-%d")
        
        # Buscar hora (ej. '15:30' o '15 hs' o '15')
        match_time = re.search(r"(\d{2}):(\d{2})", text)
        if match_time:
            time_str = f"{match_time.group(1)}:{match_time.group(2)}"
        else:
            match_hour = re.search(r"(?:a las|a las\s)(\d{2})", text)
            if match_hour:
                time_str = f"{match_hour.group(1)}:00"
            else:
                time_str = "15:00" # Por defecto
                
        return date_str, time_str

    def process_message(self, client_name, client_phone, message):
        """
        Bucle de decisión ReAct para agendar o proponer turnos.
        """
        message_lower = message.lower()
        
        # Extraer barbero de preferencia
        barbero_pref = None
        if "lucas" in message_lower:
            barbero_pref = "Lucas"
        elif "martin" in message_lower or "martín" in message_lower:
            barbero_pref = "Martín"
            
        date_str, time_str = self.parse_date_time(message)
        fecha_hora_solicitada = f"{date_str} {time_str}"
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # 1. Obtener ID del barbero si fue especificado
        barbero_id = None
        if barbero_pref:
            cursor.execute("SELECT id FROM barberos WHERE nombre = ?", (barbero_pref,))
            row = cursor.fetchone()
            if row:
                barbero_id = row[0]
                
        # 2. Si no hay barbero preferido, asignar uno disponible
        if not barbero_id:
            cursor.execute("SELECT id, nombre FROM barberos ORDER BY RANDOM() LIMIT 1")
            row = cursor.fetchone()
            barbero_id = row[0]
            barbero_pref = row[1]
            
        # 3. Verificar si el barbero está libre en esa fecha y hora
        # Consideramos conflicto si ya tiene un turno en esa hora exacta (o rango de 30 mins)
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
            
            return {
                "status": "confirmed",
                "response": f"¡Turno confirmado para {client_name}! Corte programado para el día {date_str} a las {time_str} hs con el barbero {barbero_pref}."
            }
        else:
            # Bucle de alternativas: buscar otros horarios del mismo barbero o el mismo horario con otro
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
            
            # Formular la propuesta alternativa de forma inteligente
            alternativas_msg = f"Disculpas, {barbero_pref} ya se encuentra ocupado a las {time_str} el día {date_str}.\n"
            if otro_libre:
                alternativas_msg += f"• ¿Te gustaría agendar a esa misma hora ({time_str} hs) con el barbero {otro_barbero[1]}?\n"
            if libres_mismo_barbero:
                alternativas_msg += f"• U optar por {barbero_pref} ese mismo día en los horarios: {', '.join(libres_mismo_barbero)} hs."
            else:
                alternativas_msg += f"• O probar en otra fecha cercana."
                
            return {
                "status": "suggested_alternatives",
                "response": alternativas_msg,
                "alternativas": {
                    "otro_barbero_libre": otro_libre,
                    "otro_barbero_nombre": otro_barbero[1] if (otro_barbero and otro_libre) else None,
                    "horarios_libres_mismo_barbero": libres_mismo_barbero,
                    "fecha": date_str,
                    "barbero_id": barbero_id,
                    "barbero_nombre": barbero_pref
                }
            }


# ==========================================
# 2. FINANCE & AMORTIZATION AGENT (Liquidación)
# ==========================================

class FinanceAgent:
    def __init__(self):
        pass

    def run_monthly_closure(self, mes_ano):
        """
        Calcula la liquidación financiera del mes y aplica las comisiones dinámicas y la amortización.
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
        
        # 3. Obtener el bruto generado por cada barbero
        # (Filtramos por servicios cargados en ese mes)
        cursor.execute("""
        SELECT barbero_id, SUM(monto_cobrado) 
        FROM servicios_realizados 
        WHERE strftime('%Y-%m', fecha) = ?
        GROUP BY barbero_id
        """, (mes_ano,))
        
        servicios_por_barbero = cursor.fetchall()
        
        total_bruto_generado = sum(s[1] for s in servicios_por_barbero)
        
        # 4. Evaluación de la Comisión Dinámica
        # Si el 50% retenido por la barbería es menor que los gastos mensuales totales, se activa el 40%
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
            
        # 5. Calcular liquidación para cada barbero y guardar resultados
        reporte_barberos = []
        shop_share_total = 0.0
        barber_payout_total = 0.0
        
        for barbero_id, bruto in servicios_por_barbero:
            cursor.execute("SELECT nombre FROM barberos WHERE id = ?", (barbero_id,))
            b_nombre = cursor.fetchone()[0]
            
            payout = bruto * (comision_efectiva / 100.0)
            shop_cut = bruto * ((100.0 - comision_efectiva) / 100.0)
            
            # Obtener propinas digitales si las hubiera
            cursor.execute("""
            SELECT SUM(propina_digital) FROM servicios_realizados 
            WHERE barbero_id = ? AND strftime('%Y-%m', fecha) = ?
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
        # Ganancia Neta del Dueño = Porción de la Barbería - Gastos del Local
        ganancia_neta_dueno = shop_share_total - total_gastos_local
        
        # 7. Amortización de la inversión inicial
        # Obtener inversión total
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
        
        # Durante la fase de apertura, el 100% de la ganancia del dueño va a amortizar
        if ganancia_neta_dueno > 0 and saldo_pendiente_previo > 0:
            monto_amortizado = min(ganancia_neta_dueno, saldo_pendiente_previo)
            nuevo_saldo = saldo_pendiente_previo - monto_amortizado
            
            # Guardar registro en tabla amortizaciones
            cursor.execute("""
            INSERT INTO amortizaciones (mes_ano, monto_amortizado, saldo_pendiente)
            VALUES (?, ?, ?)
            """, (mes_ano, monto_amortizado, nuevo_saldo))
            conn.commit()
            
        conn.close()
        
        return {
            "mes_ano": mes_ano,
            "total_bruto_generado": total_bruto_generado,
            "gastos_fijos": gastos_fijos,
            "gastos_insumos": gastos_insumos,
            "total_gastos_local": total_gastos_local,
            "contingencia_comision_activa": contingencia_activa,
            "comision_aplicada": comision_efectiva,
            "retencion_local_total": shop_share_total,
            "ganancia_neta_dueno_bruta": ganancia_neta_dueno,
            "monto_amortizado_este_mes": monto_amortizado,
            "ganancia_liquida_dueño": max(0.0, ganancia_neta_dueno - monto_amortizado),
            "inversion_total_inicial": inversion_total,
            "saldo_pendiente_inversion": nuevo_saldo,
            "retorno_porcentaje": round(((inversion_total - nuevo_saldo) / inversion_total * 100) if inversion_total > 0 else 0.0, 2),
            "reporte_barberos": reporte_barberos
        }


# ==========================================
# 3. SUPPLY AGENT (Consumo de Insumos)
# ==========================================

class SupplyAgent:
    def __init__(self):
        pass

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
