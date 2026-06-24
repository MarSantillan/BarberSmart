import sqlite3
import unittest
from database import get_connection, init_db, seed_db
from agents_simulator import BookingAgent, FinanceAgent, SupplyAgent

class TestBarberiaLogic(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Asegurar inicialización de la base de datos de test
        init_db()
        seed_db()

    def setUp(self):
        # Limpiar transacciones previas de servicios y gastos de prueba
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM servicios_realizados")
        cursor.execute("DELETE FROM amortizaciones")
        cursor.execute("DELETE FROM gastos_fijos WHERE mes_ano IN ('2026-06', '2026-07')")
        
        # Cargar gastos fijos estándar para el test ($170,000 total)
        cursor.execute("INSERT INTO gastos_fijos (concepto, monto, mes_ano) VALUES ('Alquiler', 120000.0, '2026-06')")
        cursor.execute("INSERT INTO gastos_fijos (concepto, monto, mes_ano) VALUES ('Servicios', 50000.0, '2026-06')")
        
        cursor.execute("INSERT INTO gastos_fijos (concepto, monto, mes_ano) VALUES ('Alquiler', 120000.0, '2026-07')")
        cursor.execute("INSERT INTO gastos_fijos (concepto, monto, mes_ano) VALUES ('Servicios', 50000.0, '2026-07')")
        
        conn.commit()
        conn.close()

    def test_dynamic_commission_contingency_active(self):
        """
        Caso 1: El bruto generado es bajo ($100,000). El 50% de la barbería ($50,000)
        no cubre los gastos fijos ($170,000). Se activa la contingencia del 40%.
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        # Cargar cortes: $100,000 bruto total realizado por Lucas (ID 1)
        for _ in range(10):
            cursor.execute("""
            INSERT INTO servicios_realizados (turno_id, barbero_id, servicio_nombre, monto_cobrado, metodo_pago, fecha)
            VALUES (NULL, 1, 'Corte de pelo', 10000.0, 'Efectivo', '2026-06-15')
            """)
            
        conn.commit()
        conn.close()
        
        # Ejecutar cierre financiero
        finance_agent = FinanceAgent()
        report = finance_agent.run_monthly_closure("2026-06")
        
        # Aserciones
        self.assertTrue(report["contingencia_comision_activa"], "La contingencia de comisiones debería estar activa")
        self.assertEqual(report["comision_aplicada"], 40.0, "La comisión aplicada debería ser del 40% para los barberos")
        
        # Payout de Lucas (40% de 100,000 = 40,000)
        lucas_report = next(b for b in report["reporte_barberos"] if b["barbero_id"] == 1)
        self.assertEqual(lucas_report["payout_neto"], 40000.0)
        
        # Porción de la barbería (60% de 100,000 = 60,000)
        self.assertEqual(report["retencion_local_total"], 60000.0)

    def test_dynamic_commission_normal_split(self):
        """
        Caso 2: El bruto generado es alto ($500,000). El 50% de la barbería ($250,000)
        cubre con creces los gastos fijos ($170,000). Se mantiene el 50/50 estándar.
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        # Cargar cortes: $500,000 bruto total realizado por Martín (ID 2)
        for _ in range(50):
            cursor.execute("""
            INSERT INTO servicios_realizados (turno_id, barbero_id, servicio_nombre, monto_cobrado, metodo_pago, fecha)
            VALUES (NULL, 2, 'Corte y Barba', 10000.0, 'Efectivo', '2026-07-15')
            """)
            
        conn.commit()
        conn.close()
        
        # Ejecutar cierre financiero
        finance_agent = FinanceAgent()
        report = finance_agent.run_monthly_closure("2026-07")
        
        # Aserciones
        self.assertFalse(report["contingencia_comision_activa"], "La contingencia no debería estar activa")
        self.assertEqual(report["comision_aplicada"], 50.0, "La comisión aplicada debería ser del 50%")
        
        # Payout de Martín (50% de 500,000 = 250,000)
        martin_report = next(b for b in report["reporte_barberos"] if b["barbero_id"] == 2)
        self.assertEqual(martin_report["payout_neto"], 25000.0 * 10) # 250,000
        self.assertEqual(report["retencion_local_total"], 250000.0)

    def test_supply_inventory_depletion(self):
        """
        Caso 3: Validar que el stock en mililitros se descuenta correctamente y se dispara alerta.
        """
        supply_agent = SupplyAgent()
        
        # Obtener stock actual de Tintura Negra (ID 1)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ml_actuales FROM insumos WHERE id = 1")
        ml_inicial = cursor.fetchone()[0]
        conn.close()
        
        # Descontar 50 ml
        result = supply_agent.record_service_supplies(1, 50.0)
        
        self.assertEqual(result["ml_consumidos"], 50.0)
        self.assertEqual(result["ml_actual"], ml_inicial - 50.0)
        
        # Descontar 180 ml adicionales para disparar alerta de stock bajo (el total es 250ml, 15% es 37.5ml)
        result_alerta = supply_agent.record_service_supplies(1, 180.0)
        self.assertTrue(result_alerta["alerta_bajo_stock"], "Debería dispararse la alerta de bajo stock")
        self.assertIsNotNone(result_alerta["alerta_mensaje"])

if __name__ == '__main__':
    unittest.main()
