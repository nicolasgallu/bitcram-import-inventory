import asyncio
import aiohttp
from app.utils.logger import logger
from app.settings.config import URL, SECRET

async def post_item(session, item):
    """Tarea individual para cada ítem"""
    data = {
        "event_type": "update",
        "item_id": int(item['id']),
        "secret": SECRET
    }
    try:
        # Usamos un timeout corto para no quedar colgados
        async with session.post(URL, json=data, timeout=5) as response:
            # No necesitamos procesar el cuerpo, así que liberamos la conexión rápido
            return response.status
    except Exception as e:
        logger.error(f"Error enviando item {item['id']}: {e}")
        return None

async def sending_update_async(items):
    """Lanzador masivo asíncrono"""
    logger.info(f"Iniciando envío asíncrono de {len(items)} notificaciones.")
    
    # ClientSession se encarga de reutilizar las conexiones (muy eficiente)
    async with aiohttp.ClientSession() as session:
        tasks = [post_item(session, item) for item in items]
        
        # gather dispara todas las tareas y espera a que terminen 
        # sin bloquearse entre ellas
        results = await asyncio.gather(*tasks)
    
    logger.info(f"Envío completado. Respuestas recibidas: {len(results)}")

def sending_update(items):
    """Punto de entrada compatible con tu código actual"""
    if not items:
        return
    asyncio.run(sending_update_async(items))