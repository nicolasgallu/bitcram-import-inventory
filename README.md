# Bitcram Inventory Sync Job

Este servicio es un proceso de ETL (Extract, Transform, Load) diseñado para sincronizar el catálogo y stock de **Bitcram** hacia una base de datos **MySQL en Cloud SQL**. Su objetivo principal es consolidar información dispersa de múltiples endpoints de la API en una tabla maestra optimizada para el sistema interno.

## ⚙️ Arquitectura de la Solución

El proceso se divide en cuatro fases críticas:

1. **Seguridad (Secret Manager):** Obtención del Bearer Token de Bitcram de forma segura.
2. **Extracción (API REST):** Consultas paginadas y filtradas para obtener información de almacenes, listas de precios y balances de stock.
3. **Transformación (Pandas):** Normalización de tipos de datos, manejo de nulos y *merge* de catálogos con existencias físicas.
4. **Carga (SQLAlchemy + Cloud SQL Connector):** Inserción masiva de datos y ejecución de lógica de negocio mediante procedimientos almacenados.

---

## 🛠️ Componentes del Sistema

### 1. Bitcram Service (`app.service.bitcram_api`)

Encargado de la comunicación con los endpoints de Bitcram.

* **Checkout & Warehouse:** Localiza el ID del punto de venta y su depósito asociado mediante un número de checkout.
* **Price List:** Extrae la base de productos y convierte los atributos adicionales en un objeto JSON compacto.
* **Stock Info:** Obtiene el balance de productos en tiempo real filtrado por el ID del depósito.

### 2. Data Processing (`app.service.data_logic`)

Utiliza **Pandas** para realizar una unión de datos eficiente:

* Realiza un `left merge` entre el catálogo y el stock usando el `product_id`.
* Asegura la integridad de los datos (`fillna(0)`) para productos sin stock reportado.
* Normaliza los IDs a formato `string` para evitar discrepancias de tipos durante la carga.

### 3. Database Layer (`app.service.mysql_load`)

Gestiona la persistencia en **GCP Cloud SQL**:

* **Conexión Segura:** Utiliza `google-cloud-sql-connector` para evitar la exposición de IPs mediante túneles IAM.
* **Atomicidad:** Emplea transacciones (`engine.begin`) para garantizar que el `TRUNCATE` y el `INSERT` masivo se realicen correctamente o se reviertan en caso de error.
* **Post-procesamiento:** Ejecuta el procedimiento `update_mirror_raw_item_data()` para refrescar las tablas espejo de la aplicación.

---

## 🔑 Configuración del Entorno

El servicio requiere las siguientes variables de entorno definidas en un archivo `.env` o en la configuración del Job en GCP:

| Variable | Descripción |
| --- | --- |
| `PROJECT_ID` | Identificador del proyecto en Google Cloud. |
| `SECRET_ID` | Nombre del secreto que contiene el Token de Bitcram. |
| `URL_BITCRAM` | URL base de la instancia de Bitcram. |
| `CHECKOUT` | Número de checkout/punto de venta a sincronizar. |
| `INSTANCE_DB` | Connection Name de la instancia de Cloud SQL. |
| `USER_DB` / `PASSWORD_DB` | Credenciales de acceso a la base de datos. |

---

## 🚦 Flujo de Ejecución Técnico

1. **Auth:** `bitcram_secrets()` recupera el token decodificado en UTF-8.
2. **Checkout Discovery:** Se obtienen los metadatos del checkout para identificar el origen de los datos.
3. **Parallel-ready Fetch:** Se descarga la lista de precios y el stock de forma secuencial (preparado para `asyncio` en futuras versiones).
4. **Data Merge:** Se genera una lista de diccionarios con la estructura:
* `id`: Identificador único del producto.
* `data`: Atributos del producto en formato JSON.
* `stock`: Cantidad disponible (Integer).
* `updated_at`: Timestamp UTC de la sincronización.


5. **Bulk Load:** Se limpia la tabla `raw_item_data` y se insertan los nuevos registros en una sola operación transaccional.

---