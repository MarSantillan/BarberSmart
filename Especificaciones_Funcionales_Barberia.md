# Especificaciones Funcionales de la Aplicación - SmartBarber Co-pilot
Este documento detalla las reglas de negocio, flujos y especificaciones de base de datos acordadas para el desarrollo técnico de la aplicación.

---

## 1. Módulo de Gestión de Turnos (WhatsApp y Recordatorios)

* **Interfaz Conversacional:** El cliente interactúa por WhatsApp en lenguaje natural con el bot de reserva.
* **Flujo de Reserva:**
  1. El cliente solicita día, hora y/o barbero.
  2. El bot consulta la agenda. Si está libre, confirma.
  3. Si está ocupado, ofrece alternativas dinámicas (otros horarios del mismo barbero o el mismo horario con otro barbero).
  4. Una vez acordado, registra el turno en estado "Confirmado".
* **Recordatorios Automáticos:** El sistema programará notificaciones automáticas por WhatsApp en dos momentos críticos:
  1. **Primer recordatorio:** 1 día (24 horas) antes de la cita.
  2. **Segundo recordatorio:** 1 hora antes de la cita.

---

## 2. Módulo de Liquidación a Barberos (Reglas Especiales y Pagos)

* **Registro de Servicios:** Al finalizar cada corte/servicio, el barbero ingresa en su panel móvil:
  * El tipo de servicio realizado (ej. Corte, Barba, Tintura).
  * El monto efectivamente cobrado al cliente.
* **Esquema Dinámico de Comisiones (Fórmula de Viabilidad de la Barbería):**
  * **Comisión Estándar:** 50% para el barbero y 50% para la barbería.
  * **Regla de Contingencia (Cierre Mensual):** 
    * Si al finalizar el mes, la porción del 50% retenida por la barbería **no es suficiente** para cubrir los gastos fijos mensuales (Alquiler + Servicios + Insumos comprados), se activa una reducción retroactiva.
    * Los barberos pasarán a cobrar el **40%** de comisión por ese mes, y la barbería retendrá el **60%** para garantizar el pago de los costos del local.
  * **Propinas:** El barbero retiene el 100% de las propinas recibidas en efectivo. Si la propina se incluye en transferencias/tarjetas, se registrará por separado para sumársela a su liquidación neta.
  * **Métodos de Pago:** Efectivo, Transferencia y Tarjeta (Mercado Point).
  * **Política de Descuento:** Los servicios pagados en efectivo contarán con un descuento configurable (ej. 10%) sobre el precio de lista.

---

## 3. Módulo de Insumos y Gastos (Control por Volumen - ml)

* **Carga de Gastos:** Realizada manualmente por el dueño en un panel administrativo.
* **Control de Stock Fraccionado (ml):**
  * Al registrar la compra de un insumo líquido o fraccionable (ej. Tintura, Oxigenada, Champú, Loción), el dueño ingresa la cantidad total en mililitros (ml) que trae el envase.
  * Al finalizar un servicio que requiera insumos (ej. Tintura), el barbero indica en la app la cantidad exacta en mililitros utilizada durante ese servicio.
  * **Descuento Automático:** La app descuenta del stock total del producto los mililitros declarados por el barbero en ese servicio.
  * **Alertas de Reposición:** El sistema generará una alerta de stock bajo cuando el volumen restante de un producto sea menor al 15% de su envase original.

---

## 4. Módulo de Inversión Inicial y Amortización

* **Moneda del Sistema:** Pesos Argentinos ($ ARS).
* **Estructura de la Inversión Inicial:** El dueño cargará el inventario clasificado de gastos iniciales de apertura (alquiler de entrada, remodelaciones, sillones, espejos, cartelería, etc.).
* **Fórmula de Amortización (Fase de Apertura):**
  * Durante la fase de recupero, **el 100% de la ganancia neta mensual del dueño** (Ingreso de la Barbería - Gastos del Local - Alquiler) se destinará directamente a amortizar la inversión inicial.
  * El dueño percibirá $0 de retiros personales.
  * **Punto de Equilibrio (Break-Even):** Una vez que el acumulado de las amortizaciones mensuales cubra el 100% de la inversión inicial registrada, el sistema notificará el éxito financiero y habilitará al dueño a retirar ganancias netas líquidas a partir del mes siguiente.

---

## 5. Diseño de Base de Datos Propuesto (Tablas Clave)

Para respaldar estas reglas de negocio, la base de datos (SQLite) se estructurará con las siguientes tablas principales:

1. **`barberos`:** `id`, `nombre`, `telefono`, `comision_base` (por defecto 50%).
2. **`turnos`:** `id`, `cliente_nombre`, `cliente_telefono`, `barbero_id`, `fecha_hora`, `estado` (Pendiente, Confirmado, Cancelado, Realizado).
3. **`servicios_realizados`:** `id`, `turno_id`, `barbero_id`, `servicio_nombre`, `monto_cobrado`, `metodo_pago` (Efectivo, Transferencia, Tarjeta), `descuento_aplicado`, `propina_digital`, `ml_consumidos`, `insumo_id`, `fecha`.
4. **`insumos`:** `id`, `nombre`, `ml_totales`, `ml_actuales`, `precio_compra`, `fecha_compra`.
5. **`gastos_fijos`:** `id`, `concepto` (Alquiler, Luz, Internet), `monto`, `mes_ano`.
6. **`inversion_inicial`:** `id`, `rubro` (Mobiliario, Infraestructura, Herramientas), `detalle`, `monto_pesos`.
7. **`amortizaciones`:** `id`, `mes_ano`, `monto_amortizado`, `saldo_pendiente`.
