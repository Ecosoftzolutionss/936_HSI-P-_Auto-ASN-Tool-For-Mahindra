import pyodbc

from config import (
    DB_SERVER,
    DB_DATABASE,
    DB_USERNAME,
    DB_PASSWORD,
    DB_DRIVER,
)


# =========================================================
# SQL SERVER CONNECTION
# =========================================================

def get_connection():

    connection_string = (
        f"DRIVER={{{DB_DRIVER}}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_DATABASE};"
        f"UID={DB_USERNAME};"
        f"PWD={DB_PASSWORD};"
        "TrustServerCertificate=yes;"
    )

    return pyodbc.connect(
        connection_string
    )


# =========================================================
# CONNECTION TEST
# =========================================================

if __name__ == "__main__":

    connection = None

    try:

        connection = get_connection()

        print(
            "================================"
        )

        print(
            "SQL Server Connected Successfully"
        )

        print(
            "================================"
        )

    except Exception as error:

        print(
            "================================"
        )

        print(
            "Database Connection Failed"
        )

        print(
            "================================"
        )

        print(
            error
        )

    finally:

        if connection is not None:

            try:
                connection.close()

            except Exception:
                pass