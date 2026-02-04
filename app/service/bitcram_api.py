import requests
import json
import pandas as pd
import datetime
from app.utils.logger import logger

def get_checkout(url_bitcrm, checkout_number, token):

    logger.info("Requesting checkout & warehouse info.")
    checkout_resp = requests.get(
        f"{url_bitcrm}/api/checkouts/index",
        headers={"Authorization": f"Bearer {token}"},
        params={"where": json.dumps({"checkouts.checkout_number": checkout_number})}
    )
    logger.info(checkout_resp.raise_for_status())
    checkout = checkout_resp.json().get("items", [])[0]
    checkout_id = checkout.get("id")
    warehouse_id = checkout.get("warehouse", {}).get("id")
    logger.info("checkout & warehouse created.")
    return checkout_id, warehouse_id


#------------------------------------------------------------------

def get_price_list(url_bitcrm, checkout_id, token):
    
    logger.info("Requesting price list info.")
    catalog_response = requests.get(
        f"{url_bitcrm}/api/checkouts/index/{checkout_id}/price_list",
        headers={"Authorization": f"Bearer {token}"}
    )
    catalog_response.raise_for_status()
    catalog = catalog_response.json().get('items')
    df_catalog = pd.DataFrame([
        {"id":str(i.pop('product_id')),
         "data":json.dumps(i)
         } 
         for i in catalog])
    logger.info(catalog[0])
    logger.info("df catalog (from price list) created.")
    return df_catalog


#def get_costs_list(url_bitcrm, token):
#    response = requests.get(f"{url_bitcrm}/api/price_lists/index", 
#                            headers={"Authorization": f"Bearer {token}"})
#
#    print(response.json())
#    
#
#def get_costs_list(url_bitcrm, token):
#    response = requests.get(f"{url_bitcrm}/api/price_lists/index", 
#                            headers={"Authorization": f"Bearer {token}"})
#
#    print(response.json())
#


#------------------------------------------------------------------

def get_stock(url_bitcrm, warehouse_id, token):

    logger.info("Requesting stock info.")
    stock_response = requests.get(
        f"{url_bitcrm}/api/stock_items/index",
            headers={"Authorization": f"Bearer {token}"},
            params={ "list_light": "true", "where": json.dumps({ "warehouse_id": warehouse_id})}
        )
    
    stock_response.raise_for_status()

    stock = stock_response.json().get("items", [])
    df_stock = pd.DataFrame([
        {"id": str(item.get("product_id")),
         "stock": item.get("product_balance", 0)
        } 
        for item in stock
    ])
    logger.info("df stock created.")
    return df_stock
#------------------------------------------------------------------

def get_items_complete(df_catalog, df_stock, old_data):
    """"""
    logger.info("Merging stock & catalog")
    df_items = pd.merge(df_catalog, df_stock, on="id", how="left")
    df_items['stock'] = df_items['stock'].fillna(0).astype(int)

    if old_data is not None: #si tenemos datos ya en DB entonces cruzamos y filtramos solo los casos con diferencia en el campo Stock.
        df_items = pd.merge(df_items, old_data, on="id", how="left")
        df_items['prev_stock'] = df_items['prev_stock'].fillna(-1)
        df_items['prev_data'] = df_items['prev_data'].fillna(json.dumps({'price':-1}))
        df_items['price'] = df_items['data'].apply(lambda x: json.loads(x) if isinstance(x, str) else x).str.get('price').fillna(0)
        df_items['prev_price'] = df_items['prev_data'].apply(lambda x: json.loads(x) if isinstance(x, str) else x).str.get('price').fillna(-1)
        #SOLO PROCESAMOS AQUELLOS CON DIFERENCIAS.
        df_items = df_items[(df_items['stock'] != df_items['prev_stock']) | (df_items['price'] != df_items['prev_price'])]

    df_items['updated_at'] = datetime.datetime.now(datetime.timezone.utc)
    items = df_items.to_dict(orient='records')
    logger.info("Merge Completed")
    return items