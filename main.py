from app.service.secrets import bitcram_secrets
from app.service.bitcram_api import get_items_complete
from app.service.mysql_load import load_data,get_item_data
from app.service.update_event import sending_update
from app.service.notifications import enviar_mensaje_whapi
from app.utils.logger import logger

try:
    previous_data = get_item_data()
    token = bitcram_secrets()
    items = get_items_complete(previous_data, token)
    if items != []: 
        load_data(items)
        sending_update(items)

except Exception as e:
    message = f"Fallo a la hora de actualizar inventario: {e}"
    enviar_mensaje_whapi(message)
    logger.error(e)