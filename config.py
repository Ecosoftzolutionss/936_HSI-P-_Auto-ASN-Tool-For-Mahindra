import os
from pathlib import Path
from dotenv import load_dotenv
BASE_DIR=Path(__file__).resolve().parent
load_dotenv(BASE_DIR/'.env',override=True)
def req(name,default=''):
    v=os.getenv(name,default)
    if v is None or not str(v).strip(): raise RuntimeError(f"Required environment variable '{name}' is missing in {BASE_DIR/'.env'}")
    return str(v).strip()
DB_SERVER=req('DB_SERVER'); DB_USERNAME=req('DB_USERNAME'); DB_PASSWORD=req('DB_PASSWORD'); DB_DRIVER=os.getenv('DB_DRIVER','ODBC Driver 17 for SQL Server').strip(); SOURCE_DB_DATABASE=req('SOURCE_DB_DATABASE'); SETTINGS_DB_DATABASE=req('SETTINGS_DB_DATABASE')
