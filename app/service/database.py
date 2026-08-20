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

            logger.info(f"updating {len(data)} records - stage: [{stage}].")

            conn.execute(text(f"""
                INSERT INTO bitcram.raw_item_data ({fields})
                VALUES({to_update})
                ON DUPLICATE KEY UPDATE {to_update_conflict}
            """),data)
            logger.info(f"upsert Completed: [{stage}].")

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

def update_last_update(updated_at):
    """
    Updates the updated_at field for all rows in bitcram.raw_item_data.
    """
    with engine.begin() as conn:
        logger.info("Updating updated_at in bitcram.raw_item_data.")

        conn.execute(
            text("""
                UPDATE bitcram.raw_item_data
                SET updated_at = :updated_at
            """),
            {"updated_at": updated_at},
        )
        logger.info("updated_at successfully updated.")

def get_last_update():
    """"""
    with engine.begin() as conn:
        logger.info("Extracting last update date from raw_item_data (with minus 2 days.)")
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
            data -= dt.timedelta(days=2)
            return data
        else:
            return None

def get_method(data):
    """returns a single row of a get sql"""
    with engine.begin() as conn:

        q_columns = ', '.join(data.get('q_columns'))
        q_from = data.get('q_from')
        q_join =  ' '.join(data.get('q_join', ''))
        q_where  = data.get('q_where', '')
        q_limit  = data.get('q_limit', '')

        result = conn.execute(
            text(f"""
                SELECT 
                {q_columns} 
                {q_from} 
                {q_join} 
                {q_where} 
                {q_limit}
                """)
            )
        data = [dict(row) for row in result.mappings()]
        if data:
            logger.info("Data extraction completed.")
            return data
        else:
            logger.info("Data extraction failed.")
            return None