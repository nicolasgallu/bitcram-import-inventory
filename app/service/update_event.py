import asyncio
import aiohttp
from app.service.mysql_load import get_publish_items
from app.utils.logger import logger
from app.settings.config import URL, SECRET

async def post_item(session, item):
    """Tarea individual para cada ítem"""
    data = {
        "event_type": "update",
        "item_id": item['id'],
        "secret": SECRET
    }
    try:
        # Usamos un timeout corto para no quedar colgados
        async with session.post(URL, json=data, timeout=5) as response:
            # No necesitamos procesar el cuerpo, así que liberamos la conexión rápido
            return response.status
    except Exception as e:
        logger.error(f"Error sending item {item['id']}: {e}")
        return None

async def sending_update_async(published_items):
    """Lanzador masivo asíncrono"""
    logger.info(f"Starting asynchronous sending of {len(published_items)} notifications.")
    
    # ClientSession se encarga de reutilizar las conexiones (muy eficiente)
    async with aiohttp.ClientSession() as session:
        tasks = [post_item(session, item) for item in published_items]
        
        # gather dispara todas las tareas y espera a que terminen 
        # sin bloquearse entre ellas
        results = await asyncio.gather(*tasks)
    
    logger.info(f"Sending completed. Responses received: {len(results)}")

def sending_update(items):
    """Punto de entrada compatible con tu código actual"""
    
    items_id = tuple([int(i.get('id')) for i in items])
    if len(items_id) == 1:
        items_id = (str(items_id).replace(",",""))
    published_items = get_publish_items(items_id)
    
    if not published_items:
        logger.info(f"No updates to perform in Mercado Libre.")
        return
    asyncio.run(sending_update_async(published_items))