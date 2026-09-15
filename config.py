import os
from pathlib import Path

from dotenv import load_dotenv


# ================================================================
# LOAD .ENV
# ================================================================

BASE_DIR = Path(__file__).resolve().parent

ENV_FILE = BASE_DIR / ".env"

load_dotenv(
    dotenv_path=ENV_FILE
)


# ================================================================
# REQUIRED ENVIRONMENT VARIABLE
# ================================================================

def get_required_env(name):
    value = os.getenv(name)

    if value is None or not value.strip():
        raise RuntimeError(
            f"Required environment variable '{name}' "
            f"is not configured in .env"
        )

    return value.strip()


# ================================================================
# DATABASE CONFIGURATION
# ================================================================

DB_SERVER = get_required_env(
    "DB_SERVER"
)

DB_DATABASE = get_required_env(
    "DB_DATABASE"
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


# ================================================================
# OTP / EMAIL CONFIGURATION
# ================================================================

OTP_MAIL_SERVER = get_required_env(
    "OTP_MAIL_SERVER"
)

OTP_MAIL_PORT = int(
    os.getenv(
        "OTP_MAIL_PORT",
        "993"
    )
)

OTP_MAIL_USERNAME = get_required_env(
    "OTP_MAIL_USERNAME"
)

OTP_MAIL_PASSWORD = get_required_env(
    "OTP_MAIL_PASSWORD"
)

OTP_SENDER = os.getenv(
    "OTP_SENDER",
    "msetusupport-noreply@mahindramail.com"
).strip()

OTP_SUBJECT = os.getenv(
    "OTP_SUBJECT",
    "MSetu Logon OTP"
).strip()