import requests
import json
from app.utils.logger import logger
from app.settings.config import URL_BITCRAM, CHECKOUT
from app.service.database import load_data
from app.service.secrets import bitcram_secrets
from app.service.update_event import sending_update

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
    logger.info(checkout_resp.raise_for_status())
    checkout = checkout_resp.json().get("items", [])[0]
    warehouse_id = checkout.get("warehouse", {}).get("id")
    logger.info("checkout & warehouse created.")
    return warehouse_id

def aux_item_cost(product_id):
    response = requests.get(
    f"{URL_BITCRAM}/api/cost_list_items/index",
    headers=headers,
    params={
            "where": json.dumps({
            "product_id": product_id})}   
    )
    cost = response.json().get('items')
    data = [{'id': i.get('product_id'), 'cost': int(i.get('cost'))} for i in cost]
    if data != []:
        fields = 'id, cost'    
        load_data(fields, data, 'item cost')

def get_updated_item(last_updated_at):
    """
    """   
    response = requests.get(
        f"{URL_BITCRAM}/api/products/index/actions/updated",
        headers=headers,params={"since": last_updated_at})
    products_raw = response.json().get('items')
    updated_at = response.json().get('last_update')
    data = [{"id":i.pop('id'), "data":json.dumps(i), "updated_at":updated_at} for i in products_raw]

    if data != []:
        fields = 'id, data, updated_at'    
        load_data(fields, data, 'items data')
        products_id = [product.get("id") for product in data]
        aux_item_cost(products_id)


def get_updated_stock(last_updated_at):
    """
    """
    warehouse_id = aux_get_checkout(URL_BITCRAM, CHECKOUT, TOKEN)

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
    updated_at = response.json().get('last_update')
    data = [{'id': i.get('product_id'), 'stock': i.get('product_balance'), 'updated_at':updated_at} for i in stock]
    if data != []:
        fields = 'id, stock, updated_at'    
        load_data(fields, data, 'stock')
        sending_update(data)
    

def get_updated_price(last_updated_at):
    """"""
    response = requests.get(
        f"{URL_BITCRAM}/api/price_list_items/index/actions/updated",
        headers=headers,
        params={"since": last_updated_at,
                "where": json.dumps({
                "price_list_id": [251, 253]
            })}   
    )
    prices = response.json().get('items')
    updated_at = response.json().get('last_update')
    prices_meli_raw = [{'id':i.get('product_id'),'price_mercadolibre':i.get('price'),'updated_at':updated_at} for i in prices if i.get('price_list_id') == 251]
    prices_meli = [i for i in prices_meli_raw if i.get('price_mercadolibre') is not None]
    prices_tnube_raw = [{'id':i.get('product_id'),'price_tienda_nube':i.get('price'),'updated_at':updated_at} for i in prices if i.get('price_list_id') == 253]
    prices_tnube = [i for i in prices_tnube_raw if i.get('price_tienda_nube') is not None]

    if prices_meli != []:
        fields = 'id, price_mercadolibre, updated_at'    
        load_data(fields, prices_meli, 'prices (meli)')
    if prices_tnube != []:
        fields = 'id, price_tienda_nube, updated_at'    
        load_data(fields, prices_tnube, 'prices (tienda nube)')