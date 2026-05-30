from app.utils.logger import logger
from sqlalchemy import create_engine, text
from google.cloud.sql.connector import Connector
from app.settings.config import INSTANCE_DB, USER_DB, PASSWORD_DB, NAME_DB
import datetime as dt


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


def get_published_items(data):
    """"""
    with engine.begin() as conn:

        logger.info("Creating temporary table app_import.temp_item_stock_updated.")
        conn.execute(text("""CREATE TEMPORARY TABLE app_import.temp_item_stock_updated (
                     id int,
                     new_stock int
                     )
                     """))
        
        logger.info("Inserting Data inside table app_import.temp_item_stock_updated.")        
        conn.execute(text("""INSERT INTO app_import.temp_item_stock_updated (id, new_stock)
                     values (:id, :new_stock)
                     """), data)

        logger.info("Joining and returning items with updated stock.")        
        result = conn.execute(text(
                """
                SELECT 
                    id,
                    meli_id,
                    tnube_id,
                    stock,
                    new_stock,
                    variant_id
                FROM app_import.product_catalog_sync
                LEFT JOIN app_import.temp_item_stock_updated using (id)
                LEFT JOIN (
                SELECT 
                    id as attribute_id,
                    item_id as id
                FROM tienda_nube.attributes) a using (id)
                LEFT JOIN (
                SELECT 
                    attribute_id,
                    product_id as tnube_id,
                    variant_id
                FROM 
                    tienda_nube.product_status) as b using (attribute_id)
                WHERE stock != new_stock and (meli_id is not null or tnube_id is not null)
                """))

        data = [dict(row) for row in result.mappings()]
        if data:
            logger.info("Data extraction completed.")
            return data
        else:
            return []

def load_data(fields:str, data:list, stage:str):
    """"""
    try:
        with engine.begin() as conn:
            to_update = ""
            to_update_conflict = ""
            fields_aux = fields.split(',')
            for i in fields_aux:
                if i =='id':
                    to_update+= f":{i.strip()}, "
                    continue
                if i == fields_aux[-1]:
                    to_update_conflict+= f"{i} = values({i.strip()})"
                    to_update+= f":{i.strip()}"
                else:
                    to_update_conflict+= f"{i} = values({i.strip()}), "
                    to_update+= f":{i.strip()}, "

            logger.info(f"updating {len(data)} records - stage: {stage}.")

            conn.execute(text(f"""
                INSERT INTO bitcram.raw_item_data ({fields})
                VALUES({to_update})
                ON DUPLICATE KEY UPDATE {to_update_conflict}
            """),data)
            logger.info("Upsert Completed.")

    except Exception as e:
        logger.error(f"Error critico en la carga masiva: {str(e)}")
        raise e


def call_procedure():
        with engine.begin() as conn:
            logger.info("Running Procedure.")
            conn.execute(text("""CALL app_import.update_product_catalog_sync()"""))
            conn.execute(text("""CALL tienda_nube.sync_new_items()"""))
            conn.execute(text("""CALL mercadolibre.insert_new_items()"""))
            logger.info("Procedures Completed.")



def get_last_update():
    """"""
    with engine.begin() as conn:
        logger.info("Extracting last update date from raw_item_data")
        result = conn.execute(
            text(f"""
                SELECT 
                min(updated_at) as updated_at
                FROM bitcram.raw_item_data
            """)
        )
        data = [dict(row) for row in result.mappings()][0].get('updated_at')
        if data:
            logger.info("Data extraction completed.")
            data = data - dt.timedelta(days=+2)
            return data
        else:
            return None