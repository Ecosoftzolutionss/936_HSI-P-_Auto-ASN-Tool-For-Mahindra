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
        connection_string,
        timeout=30
    )


# =========================================================
# CONNECTION TEST
# =========================================================

def test_database_connection():

    connection = None
    cursor = None

    try:

        connection = get_connection()
        cursor = connection.cursor()

        # -------------------------------------------------
        # CHECK ACTUAL SERVER + DATABASE
        # -------------------------------------------------

        cursor.execute("""
            SELECT
                @@SERVERNAME AS ServerName,
                DB_NAME() AS DatabaseName
        """)

        row = cursor.fetchone()

        server_name = row[0] if row else "UNKNOWN"
        database_name = row[1] if row else "UNKNOWN"

        print("=" * 70)
        print("SQL SERVER CONNECTION TEST")
        print("=" * 70)
        print("Configured Server :", DB_SERVER)
        print("Configured DB     :", DB_DATABASE)
        print("Actual Server     :", server_name)
        print("Actual Database   :", database_name)
        print("=" * 70)

        # -------------------------------------------------
        # CHECK IRPEWBInvoice TABLE
        # -------------------------------------------------

        cursor.execute("""
            SELECT COUNT(*)
            FROM dbo.IRPEWBInvoice
        """)

        total_rows = cursor.fetchone()[0]

        print(
            "IRPEWBInvoice rows:",
            total_rows
        )

        print("=" * 70)
        print("SQL Server Connected Successfully")
        print("=" * 70)

        return True

    except Exception as error:

        print("=" * 70)
        print("DATABASE CONNECTION FAILED")
        print("=" * 70)
        print(repr(error))
        print("=" * 70)

        return False

    finally:

        if cursor is not None:

            try:
                cursor.close()
            except Exception:
                pass

        if connection is not None:

            try:
                connection.close()
            except Exception:
                pass


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    test_database_connection()