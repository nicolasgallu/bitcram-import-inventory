from app.service.secrets import bitcram_secrets
from app.service.bitcram_api import get_checkout, get_price_list, get_stock, get_items_complete
from app.service.mysql_load import load_data,get_item_data
from app.service.update_event import sending_update
from app.settings.config import URL_BITCRAM, CHECKOUT


previous_data = get_item_data()

#1 obtenemos u renovamos token
token = bitcram_secrets()

#2 obtenemos checkout & warehouse id
checkout_id, warehouse_id = get_checkout(URL_BITCRAM, CHECKOUT, token)

#3 obtenemos listado de productos
df_catalog = get_price_list(URL_BITCRAM, checkout_id, token)

#4 obtenemos stock de productos
df_stock = get_stock(URL_BITCRAM, warehouse_id, token)

#5 creamos diccionario completo.
items = get_items_complete(df_catalog, df_stock, previous_data)

#6 cargamos los casos actualizados en DB y obtenemos ID para notificacion posterior.
if items != []: 
    load_data(items)
    sending_update(items)