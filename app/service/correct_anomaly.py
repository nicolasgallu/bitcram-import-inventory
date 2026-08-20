import asyncio
import aiohttp
from app.service.secrets import meli_secrets, tienda_nube_secrets
from app.service.database import get_method
from app.utils.logger import logger


PRODUCTS_TABLE = 'product_catalog_sync'
SCHEMA_INVENTORY = 'app_import'


def get_products():
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
        'q_from': f'FROM {SCHEMA_INVENTORY}.{PRODUCTS_TABLE} as src',
        'q_join': [
            f'LEFT JOIN tienda_nube.attributes as b on b.item_id = src.id',
            f'LEFT JOIN tienda_nube.product_status as c on c.attribute_id = b.id',
        ],
        'q_where': 'WHERE src.meli_id is not null or c.product_id is not null'
    }
    item_data = get_method(query)
    return item_data


# ---------------------------------------------------------------------

async def fetch_with_retry(
    session,
    plattform,
    method,
    url,
    headers,
    json_data=None,
    max_retries=2,
):
    """Helper for network calls with retries."""
    for attempt in range(max_retries):
        params = {
            "method": method,
            "url": url,
            "headers": headers,
        }

        if json_data is not None:
            params["json"] = json_data

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


# ---------------------------------------------------------------------
# MERCADO LIBRE
# ---------------------------------------------------------------------

async def sync_mercadolibre(products):
    token = meli_secrets()
    headers = {"Authorization": f"Bearer {token}","User-Agent": "PriceSyncScript/1.0"}
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
                item.get("status") != "active"
                or item.get("catalog_listing") is True
                or len(item.get("variations", [])) > 0
            ):
                return

            db_price = int(float(db_product["price_mercadolibre"]))
            meli_price = int(float(item.get("price")))
            db_stock = db_product["stock"]
            meli_stock = item.get("available_quantity")

            if meli_price != db_price or meli_stock != db_stock:
                put_url = f"https://api.mercadolibre.com/items/{meli_id}"

                async with semaphore:
                    res = await fetch_with_retry(session, 'mercadolibre', "PUT", put_url, headers, json_data={"price": db_price, 'available_quantity':db_stock})

                if res:
                    logger.info(f"MercadoLibre: Updated item {meli_id}\n"
                                f"Stock: {meli_stock} to {db_stock}\nPrice: {meli_price} to {db_price}")
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


# ---------------------------------------------------------------------
# TIENDANUBE
# ---------------------------------------------------------------------

async def sync_tiendanube(products):
    token, user_id = tienda_nube_secrets()

    headers = {
        "Authentication": f"bearer {token}",
        "User-Agent": "YourAppName (your@email.com)",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    semaphore = asyncio.Semaphore(3)

    valid_products = [p for p in products if p.get("tnube_id") and p.get("variant_id")]

    if not valid_products:
        logger.info("Tiendanube: No products to synchronize.")
        return

    updated_count = 0
    failed_count = 0

    async with aiohttp.ClientSession() as session:

        # -------------------------------------------------------------
        # GET ALL TIENDANUBE VARIANTS
        # -------------------------------------------------------------
        all_variants = {}
        page = 1
        while True:
            products_url = f"https://api.tiendanube.com/v1/{user_id}/products?page={page}&per_page=200"
            async with semaphore:
                tn_products = await fetch_with_retry(session, "tiendanube", "GET", products_url, headers)
            if not tn_products:
                break
            for product in tn_products:
                for variant in product.get("variants", []):
                    all_variants[str(variant["id"])] = variant
            logger.info(f"Tiendanube: Loaded page {page}: ({len(tn_products)} products)")
            if len(tn_products) < 200:
                break
            page += 1
            await asyncio.sleep(1)
        logger.info(f"Tiendanube: Loaded {len(all_variants)} variants total")

        # -------------------------------------------------------------
        # FIND VARIANTS THAT NEED TO BE UPDATED
        # -------------------------------------------------------------

        products_to_update = []

        for db_product in valid_products:
            product_id = str(db_product["tnube_id"])
            variant_id = str(db_product["variant_id"])
            tn_variant = all_variants.get(variant_id)

            if not tn_variant:
                logger.warning(f"Tiendanube: Variant {variant_id} not found")
                continue

            db_price = int(float(db_product.get("price_tienda_nube")) or 0)
            tn_price = int(float(tn_variant.get("price")) or 0)

            db_stock = db_product["stock"]
            tn_stock = tn_variant["stock"]

            if tn_price != db_price or db_stock != tn_stock:
                logger.info(f"Tiendanube: Added to batch item {product_id}\n"
                                f"Stock: {tn_stock} to {db_stock}\nPrice: {tn_price} to {db_price}")
                products_to_update.append({
                    "product_id": product_id,
                    "variant_id": variant_id,
                    "price": db_price,
                    "stock": db_stock
                })

        logger.info(f"Tiendanube: {len(products_to_update)} variants need update")

        # -------------------------------------------------------------
        # BULK UPDATE
        # -------------------------------------------------------------

        bulk_url = f"https://api.tiendanube.com/v1/{user_id}/products/stock-price"
        batch_size = 50

        batches = [
            products_to_update[i:i + batch_size]
            for i in range(0, len(products_to_update), batch_size)
        ]

        logger.info(f"Tiendanube: {len(batches)} bulk batches created")

        async def update_batch(batch, batch_number):
            nonlocal updated_count, failed_count

            payload = [
                {
                    "id": item["product_id"],
                    "variants": [
                        {
                        "id": int(item["variant_id"]), 
                        "price": item["price"], 
                        "inventory_levels": [{"stock": item["stock"]}]
                        }
                    ]
                }
                for item in batch
            ]

            logger.info(f"Tiendanube: Updating batch {batch_number}/{len(batches)} ({len(batch)} variants)")

            async with semaphore:
                response = await fetch_with_retry(session, "tiendanube", "PATCH", bulk_url, headers, json_data=payload)

            if response is not None:
                updated_count += len(batch)
                logger.info(f"Tiendanube: Batch {batch_number} updated successfully")
            else:
                failed_count += len(batch)
                logger.error(f"Tiendanube: Batch {batch_number} failed")

        await asyncio.gather(*[update_batch(batch, i + 1)for i, batch in enumerate(batches)])

    logger.info(
        "--- Tiendanube Summary ---\n"
        f"Checked: {len(valid_products)}\n"
        f"Updates sent: {updated_count}\n"
        f"Failed: {failed_count}\n"
        "--------------------------"
    )

# ---------------------------------------------------------------------

async def sync_ecommerce():
    products = get_products()
    await sync_mercadolibre(products)
    await sync_tiendanube(products)