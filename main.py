from app.service.bitcram_api import (
    get_updated_item, 
    get_updated_stock, 
    get_updated_price, 
    get_updated_cost
)
from app.service.database import call_procedure, get_last_update, update_last_update
from app.service.notifications import enviar_mensaje_whapi
from app.service.correct_anomaly import sync_ecommerce
from app.utils.logger import logger
import asyncio
import datetime as dt


try:
    last_updated_at = get_last_update()
    logger.info(f"Extracting Data from date: {last_updated_at}")
    get_updated_item(last_updated_at)
    get_updated_cost(last_updated_at)
    get_updated_stock(last_updated_at)
    get_updated_price(last_updated_at)
    update_last_update(dt.datetime.now())
    call_procedure()
    asyncio.run(sync_ecommerce())

except Exception as e:
    message = f"Failed on bitcram update inventory: {e}"
    enviar_mensaje_whapi(message)
    logger.error(e)




