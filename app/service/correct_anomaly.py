
import asyncio
import aiohttp
from typing import Any, Dict, List, Optional
from app.service.secrets import meli_secrets, tienda_nube_secrets
from app.service.database import get_method
from app.utils.logger import logger

PRODUCTS_TABLE = 'product_catalog_sync'
SCHEMA_INVENTORY = 'app_import'

def get_products():
    """"""
    query = {
        'q_columns': [
            'src.id',
            'src.stock',
            'src.meli_id',
            'c.product_id as tnube_id',
            'c.variant_id',
            'src.price_mercadolibre',
            'src.price_tienda_nube'
        ],
        'q_from':f'FROM {SCHEMA_INVENTORY}.{PRODUCTS_TABLE} as src',
        'q_join':[
                f'LEFT JOIN tienda_nube.attributes as b on b.item_id = src.id',
                f'LEFT JOIN tienda_nube.product_status as c on c.attribute_id = b.id',
                  ],
        'q_where': f'WHERE src.meli_id is not null or c.product_id is not null'
        }
    item_data = get_method(query)
    return item_data

# ---------------------------------------------------------------------

async def fetch_with_retry(
    session: aiohttp.ClientSession,
    plattform:str,
    method: str,
    url: str,
    headers: Dict[str, str],
    json_data: Optional[Dict[str, Any]] = None,
    max_retries: int = 2,
) -> Optional[Any]:

    """Helper for network calls handling HTTP status retries with exponential backoff."""
    for attempt in range(max_retries):

        if plattform == 'tiendanube' and method == 'GET':
            params = {
                "method": method,
                "url": url,
                "headers": headers
            }

        else :
            params = {
                "method": method,
                "url": url,
                "headers": headers,
                "json": json_data
            }

        try:
            async with session.request(**params) as response:
                if response.status < 400:
                    return await response.json()
                body = await response.text()
                logger.warning(
                    f"HTTP {response.status} from {url}\n"
                    f"BODY: {body}\n"
                    f"Retry {attempt + 1}/{max_retries}"
                )

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning(f"Error requesting {url}: {e}. Retry {attempt + 1}/{max_retries}")

        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)

    logger.error(f"Request failed permanently for {url}")
    return None


async def sync_mercadolibre(products):
    token = meli_secrets()
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "PriceSyncScript/1.0"}
    semaphore = asyncio.Semaphore(8)

    valid_products = {p["meli_id"]: p for p in products if p.get("meli_id")}
    if not valid_products:
        logger.info("MercadoLibre: No products to synchronize.")
        return

    updated_count = 0
    failed_count = 0

    async with aiohttp.ClientSession() as session:
        meli_ids = list(valid_products.keys())
        fetched_items = {}

        for i in range(0, len(meli_ids), 20):
            batch_ids = meli_ids[i:i + 20]
            url = f"https://api.mercadolibre.com/items?ids={','.join(batch_ids)}"
            
            async with semaphore:
                batch_response = await fetch_with_retry(session, 'mercadolibre', "GET", url, headers)

            if not batch_response:
                continue

            for res in batch_response:
                if res.get("code") == 200 and "body" in res:
                    body = res["body"]
                    fetched_items[body["id"]] = body

        async def process_meli_item(meli_id, db_product):
            nonlocal updated_count, failed_count
            item = fetched_items.get(meli_id)

            if not item:
                return

            if (
                db_product.get("stock", 0) == 0
                or item.get("status") != "active"
                or item.get("catalog_listing") is True
                or len(item.get("variations", [])) > 0
            ):
                return

            db_price = db_product["price_mercadolibre"]
            current_price = item.get("price")

            if current_price != db_price:
                put_url = f"https://api.mercadolibre.com/items/{meli_id}"
                async with semaphore:
                    res = await fetch_with_retry(
                        session, 'mercadolibre', "PUT", put_url, headers, json_data={"price": db_price}
                    )

                if res:
                    logger.info(f"MercadoLibre: Updated item {meli_id} price to {db_price}")
                    updated_count += 1
                else:
                    logger.error(f"MercadoLibre: Failed updating item {meli_id}")
                    failed_count += 1

        tasks = [process_meli_item(m_id, prod) for m_id, prod in valid_products.items()]
        await asyncio.gather(*tasks)

    logger.info(
        f"--- MercadoLibre Summary ---\n"
        f"Total Processed: {len(valid_products)}\n"
        f"Updated: {updated_count}\n"
        f"Failed: {failed_count}\n"
        f"----------------------------"
    )


async def sync_tiendanube(products):
    token, user_id = tienda_nube_secrets()

    headers = {
        "Authentication": f"bearer {token}",
        "User-Agent": "YourAppName (your@email.com)",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    semaphore = asyncio.Semaphore(3)

    valid_products = [
        p for p in products
        if p.get("tnube_id")
        and p.get("variant_id")
        and p.get("stock", 0) > 0
    ]

    if not valid_products:
        logger.info("Tiendanube: No products to synchronize.")
        return

    updated_count = 0
    failed_count = 0

    async with aiohttp.ClientSession() as session:

        all_variants = {}
        page = 1
        while True:
            products_url = (
                f"https://api.tiendanube.com/v1/{user_id}/products"
                f"?page={page}&per_page=200"
            )
            async with semaphore:
                tn_products = await fetch_with_retry(
                    session,
                    "tiendanube",
                    "GET",
                    products_url,
                    headers
                )
            if not tn_products:
                break

            for product in tn_products:
                for variant in product.get("variants", []):
                    all_variants[str(variant["id"])] = variant

            logger.info(f"Tiendanube: Loaded page {page}: ({len(tn_products)} products)")

            if len(tn_products) < 200:
                break
            page += 1
            await asyncio.sleep(0.1)


        logger.info(f"Tiendanube: Loaded {len(all_variants)} variants total")


        products_to_update = []
        for db_product in valid_products:
            variant_id = str(db_product["variant_id"])
            tn_variant = all_variants.get(variant_id)
            if not tn_variant:
                logger.warning(f"Tiendanube: Variant {variant_id} not found")
                continue

            db_price = float(db_product.get("price_tienda_nube") or 0)
            tn_price = float(tn_variant.get("price") or 0)

            if tn_price != db_price:
                products_to_update.append(
                    {
                        "product_id": db_product["tnube_id"],
                        "variant_id": variant_id,
                        "price": db_product["price_tienda_nube"],
                    }
                )

        logger.info(f"Tiendanube: {len(products_to_update)} variants need update")

        async def update_variant(item):
            nonlocal updated_count, failed_count
            put_url = (
                f"https://api.tiendanube.com/v1/{user_id}"
                f"/products/{item['product_id']}"
                f"/variants/{item['variant_id']}"
            )
            payload = {"price": int(item["price"])}
            async with semaphore:
                update_res = await fetch_with_retry(
                    session,
                    "tiendanube",
                    "PUT",
                    put_url,
                    headers,
                    json_data=payload
                )

            if update_res:
                updated_count += 1
                logger.info(
                    f"Tiendanube: Updated variant "
                    f"{item['variant_id']} "
                    f"price={item['price']}"
                )

            else:
                failed_count += 1
                logger.error(
                    f"Tiendanube: Failed updating "
                    f"variant {item['variant_id']}"
                )
        await asyncio.gather(*(update_variant(item) for item in products_to_update))

    logger.info(
        "--- Tiendanube Summary ---\n"
        f"Checked: {len(valid_products)}\n"
        f"Updates sent: {updated_count}\n"
        f"Failed: {failed_count}\n"
        "--------------------------"
    )

async def sync_ecommerce():
    products = get_products()
    await sync_mercadolibre(products)
    await sync_tiendanube(products)
