import pyodbc
from config import DB_SERVER,DB_USERNAME,DB_PASSWORD,DB_DRIVER,SETTINGS_DB_DATABASE
def build_connection_string(database):
    return f"DRIVER={{{DB_DRIVER}}};SERVER={DB_SERVER};DATABASE={database};UID={DB_USERNAME};PWD={DB_PASSWORD};TrustServerCertificate=yes;"
def get_connection(database=None):
    return pyodbc.connect(build_connection_string(database or SETTINGS_DB_DATABASE),timeout=30)
def test_database_connection():
    c=get_connection(); cur=c.cursor(); cur.execute('SELECT @@SERVERNAME, DB_NAME()'); r=cur.fetchone(); cur.close(); c.close(); return r
