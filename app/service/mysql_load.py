import pandas as pd
from app.utils.logger import logger
from sqlalchemy import create_engine, text
from google.cloud.sql.connector import Connector
from app.settings.config import INSTANCE_DB, USER_DB, PASSWORD_DB, NAME_DB
    
connector = Connector() 

def getconn():
    return connector.connect(
        INSTANCE_DB,
        "pymysql",
        user=USER_DB,
        password=PASSWORD_DB,
        db=NAME_DB
    )   

engine = create_engine("mysql+pymysql://",creator=getconn )



#LOGICA PARA ACCEDER AL MELI ID
def get_publish_items(item_id):
    """"""
    with engine.begin() as conn:
        logger.info(f"Extracting items id (filtering cases with meli id)")
        result = conn.execute(
            text(f"""
                SELECT id FROM app_import.product_catalog_sync
                WHERE id in {item_id} and meli_id is not null;
            """)
        )
        data = [dict(row) for row in result.mappings()]
        if data:
            logger.info("Data extraction completed.")
            return data
        else:
            logger.info("Data extraction failed.")
            return None


def get_item_data():
    """"""
    with engine.begin() as conn:
        logger.info(f"Extracting data from raw_item_data")
        result = conn.execute(
            text("""
                 SELECT 
                 id, 
                 data as prev_data, 
                 stock as prev_stock 
                 FROM bitcram.raw_item_data""")
        )
        data = [dict(row) for row in result.mappings()]
        df_stock = pd.DataFrame([
            {"id": str(item.get("id")), "prev_data": item.get("prev_data"), "prev_stock": item.get("prev_stock")} for item in data])

        if data:
            logger.info("Data extraction completed.")
            return df_stock
        else:
            logger.info("Non Data to extract.")
            return None


def load_data(items):
    """"""
    try:
        with engine.begin() as conn:

            logger.info("Paso 1/3: Creando tabla temporal en el motor de base de datos.")
            conn.execute(text("""
                CREATE TEMPORARY TABLE temp_items_data (
                    id INT, 
                    data JSON,
                    stock INT,
                    updated_at DATETIME,
                    PRIMARY KEY (id)
                ) ENGINE=InnoDB;
            """))


            logger.info(f"Paso 2/3: Insertando {len(items)} registros en la tabla temporal.")
            conn.execute(text("""
                INSERT INTO temp_items_data (id, data, stock, updated_at) 
                VALUES (:id, :data, :stock, :updated_at)
            """), items)


            logger.info("Paso 3/3: Ejecutando UPSERT masivo desde tabla temporal.")
            conn.execute(text("""
                INSERT INTO bitcram.raw_item_data (id, data, stock, updated_at)
                SELECT id, data, stock, updated_at FROM temp_items_data
                ON DUPLICATE KEY UPDATE
                    data = VALUES(data),
                    stock = VALUES(stock),
                    updated_at = VALUES(updated_at);
            """))
            logger.info("Upsert Completed.")
            logger.info("Running Procedures.")
            conn.execute(text("""CALL `app_import`.`update_mirror_raw_item_data`()"""))
            conn.execute(text("""CALL `app_import`.`update_product_catalog_sync`()"""))
            logger.info("Procedures Completed.")

    except Exception as e:
        logger.error(f"Error critico en la carga masiva: {str(e)}")
        raise e
