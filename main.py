from app.service.get_token import obtain_token
from app.service.get_bitcram import checkout,price_list,stock,items_complete
from app.service.mysql_load import load_data

#pending traer variables desde config.settings
#crear cloudrun.yaml
#crear dockerfile (foco en livianidad y version de python 3.10)

#1 obtenemos u renovamos token
token = obtain_token(project_id, secret_id, url_bitcrm, user_bitcrm, passwrd_bitcrm)
#2 obtenemos checkout & warehouse id
checkout_id, warehouse_id = checkout(url_bitcrm, checkout_number, token)
#3 obtenemos listado de productos
df_catalog = price_list(url_bitcrm, checkout_id, token)
#4 obtenemos stock de productos
df_stock = stock(url_bitcrm, warehouse_id, token)
#5 creamos jsond e inventario completo mergeando productos con stock
items = items_complete(df_catalog, df_stock)
#6 cargamos data en nuestra intancia de MYSQL
load_data(items, instance_db, user_db, passwrd_db, name_db)
