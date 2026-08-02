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
        conn.execute(text("""
        CREATE TEMPORARY TABLE app_import.temp_item_stock_updated (
            id INT,
            new_stock INT,
            price_mercadolibre INT,
            price_tienda_nube INT,
            price_mercadolibre_updated_at DATETIME,
            price_tienda_nube_updated_at DATETIME
        )
        """))
        
        logger.info("Inserting Data inside table app_import.temp_item_stock_updated.")        
        conn.execute(text("""
        INSERT INTO app_import.temp_item_stock_updated (
            id, 
            new_stock, 
            price_mercadolibre, 
            price_tienda_nube, 
            price_mercadolibre_updated_at, 
            price_tienda_nube_updated_at
        )
        VALUES (
            :id, 
            :new_stock, 
            :price_mercadolibre, 
            :price_tienda_nube, 
            :price_mercadolibre_updated_at, 
            :price_tienda_nube_updated_at
        )
        """), data)

        logger.info("Joining and returning items with updated stock.")        
        result = conn.execute(text(
        """
        SELECT
            pcs.id,
            pcs.meli_id,
            b.tnube_id,
            b.variant_id,
            tisu.new_stock,
        
            CASE
                WHEN tisu.price_mercadolibre_updated_at > pcs.price_meli_updated_at
                THEN tisu.price_mercadolibre
                ELSE NULL
            END AS price_mercadolibre,
        
            CASE
                WHEN tisu.price_tienda_nube_updated_at > pcs.price_tnube_updated_at
                THEN tisu.price_tienda_nube
                ELSE NULL
            END AS price_tienda_nube
        
        FROM app_import.product_catalog_sync AS pcs
        LEFT JOIN app_import.temp_item_stock_updated AS tisu ON pcs.id = tisu.id
        LEFT JOIN (
            SELECT
                id AS attribute_id,
                item_id AS id
            FROM tienda_nube.attributes
        ) AS a
            ON pcs.id = a.id
        LEFT JOIN (
            SELECT
                attribute_id,
                product_id AS tnube_id,
                variant_id
            FROM tienda_nube.product_status
        ) AS b ON a.attribute_id = b.attribute_id
        WHERE 
        (tisu.new_stock <> pcs.stock OR 
        tisu.price_mercadolibre_updated_at > pcs.price_meli_updated_at OR 
        tisu.price_tienda_nube_updated_at > pcs.price_tnube_updated_at ) AND 
        (pcs.meli_id IS NOT NULL OR b.tnube_id IS NOT NULL);
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