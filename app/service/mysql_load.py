from app.utils.logger import logger
from sqlalchemy import create_engine, text
from google.cloud.sql.connector import Connector
from app.settings.config import INSTANCE_DB, USER_DB, PASSWORD_DB, NAME_DB


def load_data(items):
    logger.info(f"Records to Load: {len(items)}")
    
    connector = Connector() 

    def getconn():
        return connector.connect(
            INSTANCE_DB,
            "pymysql",
            user=USER_DB,
            password=PASSWORD_DB,
            db=NAME_DB
        )   

    engine = create_engine(
        "mysql+pymysql://",
        creator=getconn,
    )

    logger.info(f"Registros a cargar: {len(items)}")

    with engine.begin() as conn:

        conn.execute(text("TRUNCATE TABLE bitcram.raw_item_data"))
        logger.info("Truncate of raw_item_data Done.")

        logger.info("Starting Massive Data Load")
        conn.execute(
            text("""
                INSERT INTO bitcram.raw_item_data (id, data, stock, updated_at)
                VALUES (:id, :data, :stock, :updated_at)
            """),
            items,
        )    
        logger.info("Load Completed")    
        logger.info("Running Procedures.")
        conn.execute(text("""CALL `app_import`.`update_mirror_raw_item_data`()"""))
        logger.info("Procedures Completed.")
