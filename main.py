from app.service.bitcram_api import (
    get_updated_item, 
    get_updated_stock, 
    get_updated_price, 
    get_updated_cost
)
from app.service.database import call_procedure, get_last_update, update_last_update
from app.service.update_event import sending_update
from app.service.notifications import enviar_mensaje_whapi
from app.service.correct_anomaly import sync_ecommerce
from app.utils.logger import logger
import asyncio
import pandas as pd
import datetime as dt

def safe_dataframe(data):
    if not data:
        return pd.DataFrame(columns=["id"])

    return pd.DataFrame(data).drop(columns=["updated_at"], errors="ignore")

try:

    last_updated_at = get_last_update()
    logger.info(f"Extracting Data from date: {last_updated_at}")
    get_updated_item(last_updated_at)
    get_updated_cost(last_updated_at)
    stock = get_updated_stock(last_updated_at)
    prices_meli, prices_tnube = get_updated_price(last_updated_at)

    update_last_update(dt.datetime.now())

    df_stock = safe_dataframe(stock)
    df_meli = safe_dataframe(prices_meli)
    df_tnube = safe_dataframe(prices_tnube)

    df = df_stock.merge(df_meli, on="id", how="outer").merge(
        df_tnube, on="id", how="outer"
    )
    df["new_stock"] = df["stock"].where(df["stock"].isna() | (df["stock"] >= 0),0)
    df = df.astype(object).where(pd.notna(df), None)
    data = df.to_dict(orient="records")

    sending_update(data)
    
    call_procedure()

    asyncio.run(sync_ecommerce())

except Exception as e:
    message = f"Fallo a la hora de actualizar inventario: {e}"
    enviar_mensaje_whapi(message)
    logger.error(e)




