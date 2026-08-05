import requests
import json
from app.utils.logger import logger
from app.settings.config import URL_BITCRAM, CHECKOUT
from app.service.database import load_data
from app.service.secrets import bitcram_secrets

TOKEN = bitcram_secrets()

headers = {"Authorization": f"Bearer {TOKEN}"}

def aux_get_checkout():
    """"""
    logger.info("Requesting checkout & warehouse info.")
    checkout_resp = requests.get(
        f"{URL_BITCRAM}/api/checkouts/index",
        headers=headers,
        params={"where": json.dumps({"checkouts.checkout_number": CHECKOUT})}
    )
    checkout = checkout_resp.json().get("items", [])[0]
    warehouse_id = checkout.get("warehouse", {}).get("id")
    logger.info("checkout & warehouse created.")
    return warehouse_id

def get_updated_item(last_updated_at=None):
    """
    """   
    warehouse_id = aux_get_checkout()
    print(warehouse_id)
    response = requests.get(
        f"{URL_BITCRAM}/api/products/index/actions/updated",
        headers=headers,params={"since": last_updated_at})
    products_raw = response.json().get('items')
    data = [{"id":i.pop('id'), "data":json.dumps(i)} for i in products_raw]
    if data != []:
        fields = 'id, data'    
        load_data(fields, data, 'items data')

def get_updated_stock(last_updated_at=None):
    """
    """
    warehouse_id = aux_get_checkout()
    response = requests.get(
        f"{URL_BITCRAM}/api/stock_items/index/actions/updated",
        headers=headers,
        params={
            "since": last_updated_at,
            "where": json.dumps({
                "warehouse_id": warehouse_id
            })
        }
    )
    stock = response.json().get('items')
    data = [{'id': i.get('product_id'), 'stock': i.get('product_balance')} for i in stock]
    if data != []:
        logger.info(f"New updated records from stock: {len(data)}")
        fields = 'id, stock'    
        load_data(fields, data, 'stock')
    return data
    
def get_updated_cost(last_updated_at=None):
    """
    """   
    response = requests.get(
        f"{URL_BITCRAM}/api/cost_list_items/index/actions/updated",
        headers=headers,params={"since": last_updated_at})
    costs_raw = response.json().get('items')
    data = [{"id":i.get('product_id'), "cost":i.get('cost')} for i in costs_raw]
    if data != []:
        fields = 'id, cost'    
        load_data(fields, data, 'cost data')

def get_updated_price(last_updated_at=None):
    """"""
    response = requests.get(
        f"{URL_BITCRAM}/api/price_list_items/index/actions/updated",
        headers=headers,
        params={"since": last_updated_at,
                "where": json.dumps({
                "price_list_id": [251, 253, 248]
            })}   
    )
    prices = response.json().get('items')
    prices_base = [{'id':i.get('product_id'), 'price':i.get('price')} for i in prices if i.get('price_list_id') == 248]
    prices_base = [i for i in prices_base if i.get('price') is not None]

    prices_meli_raw = [{'id':i.get('product_id'),'price_mercadolibre':i.get('price'),'price_mercadolibre_updated_at':i.get('last_update')} for i in prices if i.get('price_list_id') == 251]
    prices_meli = [i for i in prices_meli_raw if i.get('price_mercadolibre') is not None]

    prices_tnube_raw = [{'id':i.get('product_id'),'price_tienda_nube':i.get('price'), 'price_tienda_nube_updated_at':i.get('last_update')} for i in prices if i.get('price_list_id') == 253]
    prices_tnube = [i for i in prices_tnube_raw if i.get('price_tienda_nube') is not None]

    if prices_base != []:
        logger.info(f"New updated records from prices (base): {len(prices_base)}")
        fields = 'id, price'
        load_data(fields, prices_base, 'prices (mayorista)')
    if prices_meli != []:
        logger.info(f"New updated records from prices meli: {len(prices_meli)}")
        fields = 'id, price_mercadolibre, price_mercadolibre_updated_at'
        load_data(fields, prices_meli, 'prices (meli)')
    if prices_tnube != []:
        logger.info(f"New updated records from prices tnube: {len(prices_tnube)}")
        fields = 'id, price_tienda_nube, price_tienda_nube_updated_at'    
        load_data(fields, prices_tnube, 'prices (tienda nube)')

    return prices_meli, prices_tnube