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


def get_publish_items(item_id):
    """"""
    with engine.begin() as conn:
        logger.info(f"Extracting items id (filtering cases with meli id)")
        result = conn.execute(
            text(f"""
                SELECT 
                id 
                FROM app_import.product_catalog_sync
                WHERE id in {item_id} and meli_id is not null;
            """)
        )
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
            logger.info("Procedures Completed.")



def get_last_update():
    """"""
    with engine.begin() as conn:
        logger.info("Extracting last update date from raw_item_data")
        result = conn.execute(
            text(f"""
                SELECT 
                max(updated_at) as updated_at
                FROM bitcram.raw_item_data
            """)
        )
        data = [dict(row) for row in result.mappings()][0].get('updated_at')
        if data:
            logger.info("Data extraction completed.")
            return data
        else:
            return None