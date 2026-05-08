from app.service.database import get_published_items
from app.service.secrets import meli_secrets, tienda_nube_secrets
from app.service.notifications import enviar_mensaje_whapi
from app.utils.logger import logger
import requests
import json
import time

def sending_update(data:list):
    lst_items = [{'id': i.get('id'), 'new_stock': 0 if i.get('stock')<0 else i.get('stock')} for i in data]
    published_items = get_published_items(lst_items)
    
    def _item_status(meli_id, token):
        logger.info(f"Validating current status for item: {meli_id}")
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"https://api.mercadolibre.com/items/{meli_id}", 
            headers=headers
        )
        status = response.json().get('status')
        sub_status = next(iter(response.json().get('sub_status') or []), 'good')
        logger.info(f"status output: {status} : {sub_status}")
        return status,sub_status

    def _update_stock_meli():
        """Update MercadoLibre item"""  
        token = meli_secrets()
        for item in for_meli_cases:

            new_data = {"available_quantity": item.get('new_stock')}
            meli_id = item.get('meli_id')

            status,sub_status = _item_status(meli_id, token)

            if status == 'under_review' and sub_status == 'forbidden' or status == 'inactive' and sub_status == 'pending_documentation':
                logger.info("Product Forbidden, passing..")
                continue

            for i in range(5):
                logger.info(f"Intento Numero {i} for item {meli_id}")
                response = requests.put(f"https://api.mercadolibre.com/items/{meli_id}", 
                            json=new_data, 
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

    def _update_stock_tnube():
        """Update Tiendanube item"""  
        token, user_id = tienda_nube_secrets()
        for item in for_tnube_cases:
            variant_data = [{"stock": item.get('new_stock')}]
            tnube_id = item.get('tnube_id')
            variant_id = item.get('variant_id')
            url = f"https://api.tiendanube.com/v1/{user_id}/products/{tnube_id}/variants/{variant_id}"
            headers = {
                "Authentication": f"bearer {token}",
                "Content-Type": "application/json"}
            response = requests.put(url, headers=headers, data=json.dumps(variant_data[0]))
            logger.info(response.status_code)
            if response.status_code >300:
                message= f"""Error while trying to update stock from TiendaNube: {tnube_id}
                    error: {response.json()}"""
                logger.error(message)
                enviar_mensaje_whapi(message)
                logger.info("sleeping 1 seconds..")
                time.sleep(5)

    if published_items:
        logger.info(f"Products to update on Ecommerce Plattforms: {len(published_items)}")
        for_meli_cases = [{'meli_id': i.get('meli_id'), 'new_stock': i.get('new_stock')} for i in published_items if i.get('meli_id') and i.get('meli_id')]
        for_tnube_cases = [{'tnube_id': i.get('tnube_id'),'variant_id': i.get('variant_id'), 'new_stock': i.get('new_stock')} for i in published_items if i.get('tnube_id') and i.get('tnube_id')]

        if for_meli_cases:
            _update_stock_meli()
        if for_tnube_cases:
            _update_stock_tnube()

    else:
        logger.info("There are not items to update in Ecommerce plattforms.")