from app.service.bitcram_api import get_updated_item, get_updated_stock, get_updated_price
from app.service.database import call_procedure,get_last_update
from app.service.notifications import enviar_mensaje_whapi
from app.utils.logger import logger

try:
    last_updated_at = get_last_update()
    get_updated_item(last_updated_at)
    get_updated_stock(last_updated_at)
    get_updated_price(last_updated_at)
    call_procedure()

except Exception as e:
    message = f"Fallo a la hora de actualizar inventario: {e}"
    enviar_mensaje_whapi(message)
    logger.error(e)