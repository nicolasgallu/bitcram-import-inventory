from app.utils.logger import logger
from sqlalchemy import create_engine, text
from google.cloud.sql.connector import Connector

def load_data(items, instance_db, user_db, passwrd_db, name_db):

    logger.info(f"Records to Load: {len(items)}")

    connector = Connector() 

    def getconn():
        return connector.connect(
            instance_db,
            "pymysql",
            user=user_db,
            password=passwrd_db,
            db=name_db,
        )   

    engine = create_engine(
        "mysql+pymysql://",
        creator=getconn,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=2,
    )

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
        conn.execute(text("""CALL `app_import`.`update_item_status`();"""))
        conn.execute(text("""CALL `app_import`.`update_item_extension`();"""))
        logger.info("Procedures Completed.")

    engine.dispose()
    connector.close()
