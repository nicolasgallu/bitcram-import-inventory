from google.cloud import secretmanager
from app.settings.config import PROJECT_ID, SECRET_ID
from app.utils.logger import logger

def bitcram_secrets():
    logger.info("Getting secrets from Bitcram Account")
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{SECRET_ID}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    token = response.payload.data.decode("UTF-8")

    if token:
        logger.info("Secrets from Bitcram obtained")
        return token
    else:
        logger.error("Failed to get secrets from Bitcram")
        return None
    