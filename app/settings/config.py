import os
from dotenv import load_dotenv
load_dotenv()

PROJECT_ID=os.getenv("PROJECT_ID")
SECRET_ID=os.getenv("SECRET_ID")

URL_BITCRAM=os.getenv("URL_BITCRAM")
CHECKOUT=os.getenv("CHECKOUT")

INSTANCE_DB=os.getenv("INSTANCE_DB")
USER_DB=os.getenv("USER_DB")
PASSWORD_DB=os.getenv("PASSWORD_DB")
NAME_DB=os.getenv("NAME_DB")

URL=os.getenv("URL")
SECRET=os.getenv("SECRET")
