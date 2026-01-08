import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()  # charge les variables du fichier .env

def get_db():
    mongo_uri = os.getenv("MONGO_URI")
    db_name = os.getenv("DB_NAME")
    client = MongoClient(mongo_uri)
    return client[db_name]

