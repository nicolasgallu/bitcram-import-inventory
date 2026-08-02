from app.service.database import get_published_items
from app.service.secrets import meli_secrets, tienda_nube_secrets
from app.service.notifications import enviar_mensaje_whapi
from app.utils.logger import logger
import requests
import json
import time

def _item_status(meli_id, token):
    logger.info(f"Validating current status for item: {meli_id}")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"https://api.mercadolibre.com/items/{meli_id}",
        headers=headers
    )
    data = response.json()
    status = data.get("status")
    sub_status = next(iter(data.get("sub_status") or []), "good")
    variations_count = len(data.get("variations", []))
    logger.info(
        f"status output: {status} : {sub_status} | variations: {variations_count}"
    )
    return status, sub_status, variations_count

def update_meli(for_meli_cases):
    """Update MercadoLibre item"""  
    token = meli_secrets()
    for item in for_meli_cases:
        logger.info(item)
        payload = {
            "available_quantity": item.get('new_stock'),
            "price": str(item.get('price_mercadolibre'))
            }
        
        if item.get('new_stock') is None:
            logger.info("[Stock] deleted from update payload")
            del payload["available_quantity"]

        if item.get('price_mercadolibre') is None:
            logger.info("[Price] deleted from update payload")
            del payload["price"]


        meli_id = item.get('meli_id')
        status,sub_status,variations_count = _item_status(meli_id, token)
        if status == 'under_review' and sub_status == 'forbidden' or status == 'inactive':
            logger.info("Product Forbidden, passing..")
            continue
        if variations_count >0:
            logger.info("Product with variations, passing..")
            continue
        for i in range(5):
            logger.info(f"Intento Numero {i} for item {meli_id}")
            response = requests.put(f"https://api.mercadolibre.com/items/{meli_id}", 
                        json=payload, 
                        headers={"Authorization": f"Bearer {token}"})
            logger.info(response.status_code)
            if response.json().get('error') == 'too_many_requests':
                time.sleep(10)
            else:
                break
        if response.status_code >300:
            message= f"""Error while trying to update stock from Mercadolibre: {meli_id}
                error: {response.json()}"""
            logger.error(message)
            enviar_mensaje_whapi(message)
            logger.info("sleeping 5 seconds..")
            time.sleep(5)

def update_tnube(for_tnube_cases):
    """Update Tiendanube item"""  
    token, user_id = tienda_nube_secrets()
    for item in for_tnube_cases:

        logger.info(item)
        payload = {
            "stock": item.get('new_stock'),
            "price": item.get('price_tienda_nube')
            }
        
        if item.get('new_stock') is None:
            logger.info("[Stock] deleted from update payload")
            del payload["stock"]

        if item.get('price_tienda_nube') is None:
            logger.info("[Price] deleted from update payload")
            del payload["price"]


        if not payload:
            continue
        tnube_id = item.get('tnube_id')
        variant_id = item.get('variant_id')
        url = f"https://api.tiendanube.com/v1/{user_id}/products/{tnube_id}/variants/{variant_id}"
        headers = {
            "Authentication": f"bearer {token}",
            "Content-Type": "application/json"}
        response = requests.put(url, headers=headers, data=json.dumps(payload))
        logger.info(response.status_code)
        if response.status_code >300:
            message= f"""Error while trying to update stock from TiendaNube: {tnube_id}
                error: {response.json()}"""
            logger.error(message)
            enviar_mensaje_whapi(message)
            logger.info("sleeping 1 seconds..")
            time.sleep(5)



def sending_update(data:list):
    if data is None:
        return

    items_to_update = get_published_items(data)

    #si algun price o stock es null, se deja como null y se ignora en la carga del payload.
    
    if items_to_update:
        logger.info(f"Products to update on Ecommerce Plattforms: {len(items_to_update)}")

        for_meli_cases = [
            {'meli_id': i.get('meli_id'), 
            'new_stock': i.get('new_stock'), 
            'price_mercadolibre': i.get('price_mercadolibre')
            } 
            for i in items_to_update if i.get('meli_id')]
        
        for_tnube_cases = [
            {'tnube_id': i.get('tnube_id'),
            'variant_id': i.get('variant_id'), 
            'new_stock': i.get('new_stock'), 
            'price_tienda_nube': i.get('price_tienda_nube')
            } 
            for i in items_to_update if i.get('tnube_id')]

        if for_meli_cases:
            logger.info(f"Products to update on Mercadolibre: {len(for_meli_cases)}")
            update_meli(for_meli_cases)
        if for_tnube_cases:
            logger.info(f"Products to update on Tiendanube: {len(for_tnube_cases)}")
            update_tnube(for_tnube_cases)
        return

    else:
        logger.info("There are not items to update in Ecommerce plattforms.")
        return

        
