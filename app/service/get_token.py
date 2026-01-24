import requests
import datetime
from app.utils.logger import logger
from google.cloud import secretmanager

def obtain_token(project_id, secret_id, url_bitcrm, user_bitcrm, passwrd_bitcrm):

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    version = client.get_secret_version(request={"name": name})  

    #check vencimiento
    fecha_creacion = version.create_time 
    ahora = datetime.datetime.now(datetime.timezone.utc)
    antiguedad = ahora - fecha_creacion
    if antiguedad.days < 5:
        token = response.payload.data.decode("UTF-8")
        logger.info("Using existing Token.")
        return token
    else:
        logger.warning("Renovating Token.")

        auth = requests.post(
            f"{url_bitcrm}/api/auth/",
            json={"username": user_bitcrm, "password": passwrd_bitcrm}
        )

        auth.raise_for_status()
        token = auth.json()["token"]
        client.add_secret_version(
            parent=f"projects/{project_id}/secrets/{secret_id}",
            payload={"data": token.encode("UTF-8")}
        )
        logger.info("New token generated and saved")
        return token
