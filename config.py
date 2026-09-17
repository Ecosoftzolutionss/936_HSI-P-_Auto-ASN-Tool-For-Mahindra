import os
from pathlib import Path

from dotenv import load_dotenv


# =========================================================
# LOAD .ENV
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

print("==============================================")
print("CONFIGURATION")
print("==============================================")
print("Python Base Directory :", BASE_DIR)
print(".env Path             :", ENV_FILE)
print(".env Exists           :", ENV_FILE.exists())
print("==============================================")


if not ENV_FILE.exists():
    raise RuntimeError(
        f".env file not found at:\n{ENV_FILE}"
    )


load_dotenv(
    dotenv_path=ENV_FILE,
    override=True
)


# =========================================================
# REQUIRED ENVIRONMENT VARIABLE
# =========================================================

def get_required_env(name):

    value = os.getenv(name)

    if value is None or not value.strip():

        raise RuntimeError(
            f"Required environment variable '{name}' "
            f"is not configured in:\n{ENV_FILE}"
        )

    return value.strip()


# =========================================================
# SQL SERVER - COMMON
# =========================================================

DB_SERVER = get_required_env(
    "DB_SERVER"
)

DB_USERNAME = get_required_env(
    "DB_USERNAME"
)

DB_PASSWORD = get_required_env(
    "DB_PASSWORD"
)

DB_DRIVER = os.getenv(
    "DB_DRIVER",
    "ODBC Driver 17 for SQL Server"
).strip()


# =========================================================
# MAIN APPLICATION DATABASE
#
# Existing application:
#   main.py
#   login.py
#   database.py
#
# Primary:
#   DB_DATABASE
#
# Fallback:
#   SETTINGS_DB_DATABASE
# =========================================================

DB_DATABASE = os.getenv(
    "DB_DATABASE"
)

if DB_DATABASE is None or not DB_DATABASE.strip():

    DB_DATABASE = os.getenv(
        "SETTINGS_DB_DATABASE"
    )

if DB_DATABASE is None or not DB_DATABASE.strip():

    raise RuntimeError(
        "Neither DB_DATABASE nor SETTINGS_DB_DATABASE "
        "is configured in .env"
    )

DB_DATABASE = DB_DATABASE.strip()


# =========================================================
# IRP SOURCE DATABASE
#
# Contains:
#   IRPEWBMulti_Part_Details
#   IRPEWBInvoice
# =========================================================

SOURCE_DB_DATABASE = get_required_env(
    "SOURCE_DB_DATABASE"
)


# =========================================================
# SETTINGS DATABASE
#
# Contains:
#   dbo.SETTINGS
#   dbo.MailSettings
#   F_PATH
#
# OTP mail configuration is NOT stored in .env.
# OTP mail configuration is loaded dynamically from
# dbo.MailSettings by the automation.
# =========================================================

SETTINGS_DB_DATABASE = get_required_env(
    "SETTINGS_DB_DATABASE"
)


# =========================================================
# CONFIGURATION SUMMARY
# =========================================================

print("MAIN DB              :", DB_DATABASE)
print("IRP SOURCE DB        :", SOURCE_DB_DATABASE)
print("SETTINGS DB          :", SETTINGS_DB_DATABASE)
print("SQL SERVER           :", DB_SERVER)
print("SQL DRIVER           :", DB_DRIVER)
print("OTP MAIL CONFIG      : dbo.MailSettings")
print("==============================================")