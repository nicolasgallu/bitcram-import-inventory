# Bitcram Inventory Sync Job

Este servicio es un proceso de ETL (Extract, Transform, Load) diseñado para sincronizar el catálogo y stock de Bitcram hacia una base de datos MySQL en Cloud SQL. El sistema está optimizado para procesar únicamente cambios (**deltas**) y disparar actualizaciones en tiempo real hacia Mercado Libre.

## ⚙️ Arquitectura de la Solución

El proceso se divide en cinco fases críticas:

1. **Seguridad (Secret Manager):** Obtención del Bearer Token de Bitcram de forma segura.
2. **Extracción (API REST):** Consultas paginadas para obtener información de almacenes, precios y stock.
3. **Transformación y Detección de Cambios (Pandas):** Comparación del estado actual vs. el estado anterior para identificar variaciones en **stock** o **precio**.
4. **Carga Eficiente (UPSERT):** Inserción de nuevos productos y actualización de los existentes mediante una tabla temporal y lógica de `ON DUPLICATE KEY UPDATE`.
5. **Notificación (Asynchronous Webhooks):** Disparo masivo y no bloqueante de actualizaciones hacia el microservicio de publicaciones (Meli).

## 🛠️ Componentes del Sistema

### 1. Data Processing & Delta Detection (`app.service.data_logic`)

El motor de lógica ahora es más inteligente:

* **Merge de Estados:** Realiza un `left merge` entre los datos entrantes de Bitcram y los datos existentes en la DB (`prev_stock`, `prev_data`).
* **Filtro de Variaciones:** Aísla únicamente los registros donde `stock != prev_stock` o el precio dentro del JSON `data` ha cambiado.
* **Optimización de Carga:** Solo los registros con cambios confirmados avanzan a la fase de carga, reduciendo drásticamente el uso de recursos en Cloud SQL.

### 2. Database Layer (`app.service.mysql_load`)

Gestión de persistencia optimizada:

* **Tablas Temporales:** Se utiliza una `TEMPORARY TABLE` para la carga inicial de los deltas.
* **Lógica UPSERT:** En lugar de un `TRUNCATE` destructivo, se utiliza `INSERT ... ON DUPLICATE KEY UPDATE` para mantener la integridad y disponibilidad de la tabla maestra.

### 3. Notification Engine (`app.service.update_event`)

Módulo encargado de sincronizar con el servicio de Publicaciones:

* **Async Dispatcher:** Utiliza `aiohttp` y `asyncio` para enviar múltiples payloads de actualización en paralelo.
* **Fire & Forget:** Gracias a la implementación de **Threading** en el webhook de destino, este servicio recupera el control de inmediato sin esperar el procesamiento de IA o APIs de terceros.

## 🚦 Flujo de Ejecución Técnico

1. **Auth:** `bitcram_secrets()` recupera el token decodificado.
2. **Parallel Fetch:** Descarga de lista de precios y stock.
3. **Delta Comparison:** * Se calcula la diferencia: `df_cambios = df[(stock != prev_stock) | (price != prev_price)]`.
4. **Bulk Upsert:** * Creación de tabla temporal.
* Inserción de registros detectados.
* Ejecución de `INSERT ... SELECT ... ON DUPLICATE KEY UPDATE` hacia `raw_item_data`.


5. **Webhook Trigger:** * Si existen cambios, se dispara `sending_update(items)`.
* Envío asíncrono hacia el endpoint de publicaciones para impactar en Mercado Libre.



---