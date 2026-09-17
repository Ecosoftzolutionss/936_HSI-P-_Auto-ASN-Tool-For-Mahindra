"""
===============================================================================
IRP INVOICE -> ASN CSV EXPORT
===============================================================================

FLOW:

1. Connect to SOURCE DATABASE
       HSI(P)_BKP_29082026

2. Read ALL invoice records where:
       AUTO_STATUS = 0

3. Prepare ASN CSV with the exact Excel template column names.

4. Read F_PATH dynamically from:
       HSI_Automation.dbo.SETTINGS

5. Copy CSV to F_PATH.

6. DO NOT update AUTO_STATUS here.

7. After Mahindra ASN is successfully created, call:
       update_auto_status(doc_numbers)

   This will update:
       IRPEWBInvoice.AUTO_STATUS = 1

===============================================================================
REQUIRED PACKAGES

pip install pandas pyodbc python-dotenv
===============================================================================
"""

import os
import sys
import shutil
import time

from datetime import datetime
from pathlib import Path

import pandas as pd
import pyodbc

from dotenv import load_dotenv


# =============================================================================
# LOAD .ENV
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent

ENV_FILE = BASE_DIR / ".env"

load_dotenv(
    dotenv_path=ENV_FILE,
    override=True
)


# =============================================================================
# ENVIRONMENT HELPER
# =============================================================================

def get_required_env(name):

    value = os.getenv(name)

    if value is None or not value.strip():

        raise RuntimeError(
            f"Required environment variable '{name}' "
            f"is not configured in:\n{ENV_FILE}"
        )

    return value.strip()


# =============================================================================
# COMMON SQL SERVER CONFIGURATION
# =============================================================================

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


# =============================================================================
# DATABASE 1
# SOURCE DATABASE
# =============================================================================

SOURCE_DB_DATABASE = get_required_env(
    "SOURCE_DB_DATABASE"
)


# =============================================================================
# DATABASE 2
# SETTINGS DATABASE
# =============================================================================

SETTINGS_DB_DATABASE = get_required_env(
    "SETTINGS_DB_DATABASE"
)


# =============================================================================
# OUTPUT CONFIGURATION
# =============================================================================

LOCAL_OUTPUT_FOLDER = (
    BASE_DIR / "output"
)

# =============================================================================
# ASN QUEUE FOLDERS / SCHEDULER
# =============================================================================
#
# The Excel preparation process runs independently of the HSI Automation
# application. It checks the database every 20 minutes.
#
# Pending:
#   Files waiting for Mahindra ASN upload.
#
# Completed:
#   Files whose ASN was successfully created AND AUTO_STATUS was updated to 1.
#
# IMPORTANT:
#   Only files inside Pending are considered by automation.py.
#   Existing Pending files are used to prevent the same invoice from being
#   exported again on the next 20-minute check.
# =============================================================================

PENDING_FOLDER_NAME = "Pending"
COMPLETED_FOLDER_NAME = "Completed"

CHECK_INTERVAL_SECONDS = 20 * 60

# True = remove the local staging copy after it is copied to F_PATH\Pending.
# The actual queue file remains in F_PATH\Pending.
DELETE_LOCAL_AFTER_COPY = True


# =============================================================================
# FILE NAME
# =============================================================================
#
# Example:
#
# ASN_Upload_20260916_223000.csv
#
# =============================================================================

USE_TIMESTAMP_IN_FILENAME = True


# =============================================================================
# SETTINGS
# =============================================================================

DELETE_LOCAL_AFTER_COPY = False


# =============================================================================
# ASN TEMPLATE DEFAULT VALUES
# =============================================================================

# Item Sr No is not available in the supplied database query.
#
# Your Excel template shows:
#
# Item Sr No = 10
#
ITEM_SR_NO = 10


# LR No is not available in the supplied query.
#
# Your Excel template shows:
#
# LR No = *
#
LR_NO = "*"


# =============================================================================
# EXACT ASN EXCEL COLUMN NAMES
# =============================================================================

ASN_COLUMNS = [

    "PO/SA Number",

    "Item Sr No",

    "Part No",

    "ASN Quantity",

    "Invoice No",

    "Invoice Date (dd.mm.yyyy)",

    "Invoice Amount Inclusive of TCS",

    "Excise Amount",

    "LR No",

    "LR Date (dd.mm.yyyy)",

    "Veh No",

    "Material Base Price",

    "IRN Number",

    "Vendor GST",

    "Mahindra GST",

    "Packaging Material1",

    "Packaging Material1 Quantity",

    "Packaging Material2",

    "Packaging Material2 Quantity",

    "Packaging Material3",

    "Packaging Material3 Quantity",
]


# =============================================================================
# SOURCE SQL
# =============================================================================
#
# IMPORTANT:
#
# NO DOC_NO FILTER
#
# Only:
#
# AUTO_STATUS = 0
#
# Therefore every pending invoice will be exported.
#
# =============================================================================

SOURCE_QUERY = r"""
SELECT

    D.PrdNm,

    D.Qty,

    D.TotItemVal,

    (
        ISNULL(D.CgstAmt, 0)
        +
        ISNULL(D.SgstAmt, 0)
    ) AS [Excise Amount],

    D.UnitPrice,

    I.PORef,

    I.DocNo,

    I.DocDate,

    I.VEHICLE_NO,

    I.Irn,

    I.SellDetGSTIN,

    I.BuyDetGSTIN

FROM IRPEWBMulti_Part_Details D

INNER JOIN IRPEWBInvoice I

    ON D.DocNo = I.DocNo

WHERE I.AUTO_STATUS = 0

ORDER BY I.DocDate, I.DocNo;
"""


# =============================================================================
# BUILD CONNECTION STRING
# =============================================================================

def build_connection_string(database):

    connection_string = (

        f"DRIVER={{{DB_DRIVER}}};"

        f"SERVER={DB_SERVER};"

        f"DATABASE={database};"

        f"UID={DB_USERNAME};"

        f"PWD={DB_PASSWORD};"

        "TrustServerCertificate=yes;"

    )

    return connection_string


# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_connection(database, label):

    print()
    print("=" * 80)

    print(
        f"CONNECTING TO {label}"
    )

    print("=" * 80)

    print(
        "SERVER   :",
        DB_SERVER
    )

    print(
        "DATABASE :",
        database
    )

    print(
        "USERNAME :",
        DB_USERNAME
    )

    print(
        "DRIVER   :",
        DB_DRIVER
    )

    print("=" * 80)

    try:

        connection = pyodbc.connect(

            build_connection_string(
                database
            ),

            timeout=30
        )

        print(
            f"{label} connection successful."
        )

        return connection

    except pyodbc.Error as error:

        print()
        print("=" * 80)

        print(
            f"{label} CONNECTION FAILED"
        )

        print("=" * 80)

        print(
            type(error).__name__,
            ":",
            repr(error)
        )

        print("=" * 80)

        raise


# =============================================================================
# FETCH ALL PENDING INVOICES
# =============================================================================

def fetch_pending_invoice_data():

    connection = None

    try:

        connection = get_connection(

            SOURCE_DB_DATABASE,

            "SOURCE DATABASE"
        )

        print()
        print("=" * 80)

        print(
            "READING PENDING IRP INVOICE DETAILS"
        )

        print("=" * 80)

        print(
            "DATABASE:",
            SOURCE_DB_DATABASE
        )

        print(
            "FILTER  : AUTO_STATUS = 0"
        )

        print("=" * 80)

        # ---------------------------------------------------------------------
        # Execute SQL
        # ---------------------------------------------------------------------

        dataframe = pd.read_sql_query(

            SOURCE_QUERY,

            connection
        )

        # ---------------------------------------------------------------------
        # Result
        # ---------------------------------------------------------------------

        print()

        print(
            "ROWS RETURNED:",
            len(dataframe)
        )

        if dataframe.empty:

            print()

            print("=" * 80)

            print(
                "NO PENDING INVOICES"
            )

            print("=" * 80)

            print(
                "No records found where AUTO_STATUS = 0."
            )

            return dataframe

        # ---------------------------------------------------------------------
        # Display invoice numbers
        # ---------------------------------------------------------------------

        unique_docs = (

            dataframe["DocNo"]

            .dropna()

            .astype(str)

            .str.strip()

            .unique()

        )

        print()

        print(
            "PENDING INVOICES:"
        )

        for doc_no in unique_docs:

            print(
                "   ",
                doc_no
            )

        print()

        print(
            "TOTAL INVOICES:",
            len(unique_docs)
        )

        print(
            "TOTAL ROWS:",
            len(dataframe)
        )

        print("=" * 80)

        return dataframe

    except Exception as error:

        print()
        print("=" * 80)

        print(
            "SOURCE DATA READ FAILED"
        )

        print("=" * 80)

        print(
            type(error).__name__,
            ":",
            repr(error)
        )

        print("=" * 80)

        raise

    finally:

        if connection is not None:

            try:

                connection.close()

            except Exception:

                pass

        print(
            "SOURCE DATABASE connection closed."
        )


# =============================================================================
# GET DYNAMIC F_PATH
# =============================================================================

def get_dynamic_fpath():

    connection = None

    cursor = None

    query = r"""
SELECT TOP 1

    F_PATH

FROM dbo.SETTINGS

WHERE F_PATH IS NOT NULL

  AND LTRIM(RTRIM(F_PATH)) <> ''

ORDER BY ID DESC;
"""

    try:

        connection = get_connection(

            SETTINGS_DB_DATABASE,

            "SETTINGS DATABASE"
        )

        cursor = connection.cursor()

        print()
        print("=" * 80)

        print(
            "READING DYNAMIC F_PATH"
        )

        print("=" * 80)

        print(
            "SETTINGS DATABASE:",
            SETTINGS_DB_DATABASE
        )

        print("=" * 80)

        cursor.execute(
            query
        )

        row = cursor.fetchone()

        if not row:

            raise RuntimeError(

                "No valid F_PATH found "
                "in dbo.SETTINGS."
            )

        f_path = str(

            row[0] or ""

        ).strip()

        # Remove quotes

        f_path = (

            f_path

            .strip('"')

            .strip("'")

            .strip()

        )

        # Expand environment variables

        f_path = os.path.expandvars(
            f_path
        )

        if not f_path:

            raise RuntimeError(
                "F_PATH is empty."
            )

        print()

        print(
            "DYNAMIC F_PATH:"
        )

        print(
            f_path
        )

        print("=" * 80)

        return f_path

    except Exception as error:

        print()
        print("=" * 80)

        print(
            "F_PATH READ FAILED"
        )

        print("=" * 80)

        print(
            type(error).__name__,
            ":",
            repr(error)
        )

        print("=" * 80)

        raise

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

        print(
            "SETTINGS DATABASE connection closed."
        )


# =============================================================================
# PREPARE ASN DATA
# =============================================================================

def prepare_asn_dataframe(dataframe):

    print()
    print("=" * 80)

    print(
        "PREPARING ASN EXCEL DATA"
    )

    print("=" * 80)

    asn_df = pd.DataFrame()

    # -------------------------------------------------------------------------
    # PO/SA Number
    # -------------------------------------------------------------------------

    asn_df["PO/SA Number"] = (
        dataframe["PORef"]
    )

    # -------------------------------------------------------------------------
    # Item Sr No
    # -------------------------------------------------------------------------

    asn_df["Item Sr No"] = (
        ITEM_SR_NO
    )

    # -------------------------------------------------------------------------
    # Part No
    # -------------------------------------------------------------------------

    asn_df["Part No"] = (
        dataframe["PrdNm"]
    )

    # -------------------------------------------------------------------------
    # ASN Quantity
    # -------------------------------------------------------------------------

    asn_df["ASN Quantity"] = (
        dataframe["Qty"]
    )

    # -------------------------------------------------------------------------
    # Invoice No
    # -------------------------------------------------------------------------

    asn_df["Invoice No"] = (
        dataframe["DocNo"]
    )

    # -------------------------------------------------------------------------
    # Invoice Date
    # -------------------------------------------------------------------------

    invoice_dates = pd.to_datetime(

        dataframe["DocDate"],

        errors="coerce"
    )

    asn_df[
        "Invoice Date (dd.mm.yyyy)"
    ] = (

        invoice_dates

        .dt

        .strftime("%d.%m.%Y")

    )

    # -------------------------------------------------------------------------
    # Invoice Amount Inclusive of TCS
    # -------------------------------------------------------------------------

    asn_df[
        "Invoice Amount Inclusive of TCS"
    ] = (

        dataframe["TotItemVal"]

    )

    # -------------------------------------------------------------------------
    # Excise Amount
    # -------------------------------------------------------------------------

    asn_df[
        "Excise Amount"
    ] = (

        dataframe["Excise Amount"]

    )

    # -------------------------------------------------------------------------
    # LR No
    # -------------------------------------------------------------------------

    asn_df[
        "LR No"
    ] = LR_NO

    # -------------------------------------------------------------------------
    # LR Date
    # -------------------------------------------------------------------------

    asn_df[
        "LR Date (dd.mm.yyyy)"
    ] = (

        invoice_dates

        .dt

        .strftime("%d.%m.%Y")

    )

    # -------------------------------------------------------------------------
    # Vehicle
    # -------------------------------------------------------------------------

    asn_df[
        "Veh No"
    ] = (

        dataframe["VEHICLE_NO"]

    )

    # -------------------------------------------------------------------------
    # Material Base Price
    # -------------------------------------------------------------------------

    asn_df[
        "Material Base Price"
    ] = (

        dataframe["UnitPrice"]

    )

    # -------------------------------------------------------------------------
    # IRN
    # -------------------------------------------------------------------------

    asn_df[
        "IRN Number"
    ] = (

        dataframe["Irn"]

    )

    # -------------------------------------------------------------------------
    # GST
    # -------------------------------------------------------------------------

    asn_df[
        "Vendor GST"
    ] = (

        dataframe["SellDetGSTIN"]

    )

    asn_df[
        "Mahindra GST"
    ] = (

        dataframe["BuyDetGSTIN"]

    )

    # -------------------------------------------------------------------------
    # Packaging Material
    # -------------------------------------------------------------------------

    asn_df[
        "Packaging Material1"
    ] = ""

    asn_df[
        "Packaging Material1 Quantity"
    ] = ""

    asn_df[
        "Packaging Material2"
    ] = ""

    asn_df[
        "Packaging Material2 Quantity"
    ] = ""

    asn_df[
        "Packaging Material3"
    ] = ""

    asn_df[
        "Packaging Material3 Quantity"
    ] = ""

    # -------------------------------------------------------------------------
    # Force exact column order
    # -------------------------------------------------------------------------

    asn_df = asn_df[
        ASN_COLUMNS
    ]

    print()

    print(
        "ASN ROWS:",
        len(asn_df)
    )

    print()

    print(
        "ASN COLUMNS:"
    )

    for index, column in enumerate(

        asn_df.columns,

        start=1

    ):

        print(
            f"{index:02d}. {column}"
        )

    print()

    print("=" * 80)

    return asn_df


# =============================================================================
# CREATE CSV
# =============================================================================

def create_csv(asn_dataframe):
    """
    Create a unique local CSV staging file.

    The local file is only a staging copy. The real queue is maintained in:
        F_PATH/Pending
    """

    LOCAL_OUTPUT_FOLDER.mkdir(
        parents=True,
        exist_ok=True
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )[:-3]

    filename = (
        f"ASN_Upload_{timestamp}.csv"
    )

    local_csv = (
        LOCAL_OUTPUT_FOLDER / filename
    )

    asn_dataframe.to_csv(
        local_csv,
        index=False,
        encoding="utf-8-sig"
    )

    print()
    print("=" * 80)
    print("ASN CSV CREATED")
    print("=" * 80)
    print("LOCAL FILE:", local_csv)
    print("ROWS:", len(asn_dataframe))
    print("SIZE:", local_csv.stat().st_size, "bytes")
    print("=" * 80)

    return local_csv


# =============================================================================
# PENDING QUEUE HELPERS
# =============================================================================

def get_pending_folder(f_path):
    """
    Return F_PATH/Pending and create it when necessary.
    """
    pending_folder = (
        Path(f_path) / PENDING_FOLDER_NAME
    )

    pending_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    return pending_folder


def get_completed_folder(f_path):
    """
    Return F_PATH/Completed and create it when necessary.
    """
    completed_folder = (
        Path(f_path) / COMPLETED_FOLDER_NAME
    )

    completed_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    return completed_folder


def get_pending_invoice_numbers(f_path):
    """
    Read all existing CSV files in F_PATH/Pending and return their
    Invoice No values.

    This is the duplicate-protection mechanism.

    Example:
        Pending contains ASN_090000.csv with P26101416.

        The next 20-minute database check still sees P26101416 as
        AUTO_STATUS = 0, but this function tells the exporter that
        P26101416 is already queued, so it will NOT create another CSV.
    """

    pending_folder = get_pending_folder(f_path)

    invoice_numbers = set()

    allowed_extensions = (
        ".csv",
        ".xls",
        ".xlsx",
    )

    try:
        entries = sorted(
            pending_folder.iterdir(),
            key=lambda item: item.stat().st_mtime
        )
    except Exception as error:
        print(
            "Could not read Pending folder:",
            repr(error)
        )
        return invoice_numbers

    for file_path in entries:

        if not file_path.is_file():
            continue

        if file_path.suffix.lower() not in allowed_extensions:
            continue

        # Mahindra currently consumes CSV. For duplicate detection,
        # read CSV files only. XLS/XLSX are retained as a fallback file
        # type but are not created by this exporter.
        if file_path.suffix.lower() != ".csv":
            continue

        try:
            queued_df = pd.read_csv(
                file_path,
                dtype=str,
                keep_default_na=False,
            )

            if "Invoice No" not in queued_df.columns:
                print(
                    "Pending file has no 'Invoice No' column:",
                    file_path
                )
                continue

            values = (
                queued_df["Invoice No"]
                .astype(str)
                .str.strip()
            )

            for value in values:
                if value:
                    invoice_numbers.add(value)

        except Exception as error:
            # Do not delete or modify a pending file just because it
            # could not be read. Leave it for manual inspection.
            print(
                "Could not inspect pending ASN file:",
                file_path,
                "| error:",
                repr(error)
            )

    return invoice_numbers


def copy_to_fpath(local_csv, f_path):
    """
    Copy the newly-created CSV into F_PATH/Pending.

    The Pending folder is the durable queue consumed by automation.py.
    """

    pending_folder = get_pending_folder(f_path)

    print()
    print("=" * 80)
    print("COPYING ASN CSV TO PENDING QUEUE")
    print("=" * 80)
    print("SOURCE:", local_csv)
    print("DESTINATION:", pending_folder)
    print("=" * 80)

    destination_csv = (
        pending_folder / local_csv.name
    )

    # Never overwrite an existing queue file.
    if destination_csv.exists():
        raise RuntimeError(
            f"ASN queue file already exists:\n{destination_csv}"
        )

    shutil.copy2(
        local_csv,
        destination_csv
    )

    if not destination_csv.is_file():
        raise RuntimeError(
            f"CSV was not copied to:\n{destination_csv}"
        )

    print()
    print("=" * 80)
    print("CSV ADDED TO PENDING QUEUE")
    print("=" * 80)
    print("PENDING FILE:", destination_csv)
    print("=" * 80)

    if DELETE_LOCAL_AFTER_COPY:
        try:
            local_csv.unlink()
            print(
                "Local staging CSV removed:",
                local_csv
            )
        except Exception as error:
            print(
                "Local staging CSV could not be removed:",
                repr(error)
            )

    return destination_csv


# =============================================================================
# GET EXPORTED DOCUMENT NUMBERS
# =============================================================================

def get_document_numbers(dataframe):

    document_numbers = (
        dataframe["DocNo"]
        .dropna()
        .astype(str)
        .str.strip()
        .loc[lambda x: x != ""]
        .drop_duplicates()
        .tolist()
    )

    return document_numbers


# =============================================================================
# UPDATE AUTO_STATUS = 1
# =============================================================================

def update_auto_status(document_numbers):

    if not document_numbers:
        print(
            "No document numbers supplied "
            "for AUTO_STATUS update."
        )
        return 0

    connection = None

    try:

        connection = get_connection(
            SOURCE_DB_DATABASE,
            "SOURCE DATABASE - STATUS UPDATE"
        )

        cursor = connection.cursor()

        update_query = r"""
UPDATE IRPEWBInvoice
SET AUTO_STATUS = 1
WHERE DocNo = ?
  AND AUTO_STATUS = 0;
"""

        updated_count = 0

        print()
        print("=" * 80)
        print("UPDATING AUTO_STATUS")
        print("=" * 80)

        for doc_no in document_numbers:

            cursor.execute(
                update_query,
                doc_no
            )

            row_count = cursor.rowcount

            updated_count += (
                row_count
                if row_count > 0
                else 0
            )

            print(
                f"{doc_no} -> AUTO_STATUS = 1 "
                f"(Rows updated: {row_count})"
            )

        connection.commit()

        print()
        print(
            "TOTAL ROWS UPDATED:",
            updated_count
        )
        print("=" * 80)

        return updated_count

    except Exception as error:

        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass

        print()
        print("=" * 80)
        print("AUTO_STATUS UPDATE FAILED")
        print("=" * 80)
        print(
            type(error).__name__,
            ":",
            repr(error)
        )
        print("=" * 80)

        raise

    finally:

        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

        print(
            "SOURCE DATABASE status connection closed."
        )


# =============================================================================
# ONE 20-MINUTE CHECK
# =============================================================================

def prepare_new_asn_file():
    """
    Execute ONE database check.

    Rules:
      1. Read AUTO_STATUS = 0.
      2. Read invoices already present in F_PATH/Pending.
      3. Remove already-queued invoices from the new export.
      4. If nothing new exists -> do not create a CSV.
      5. If new invoices exist -> create one new CSV.
      6. Never update AUTO_STATUS here.
    """

    print()
    print("#" * 80)
    print("ASN EXCEL PREPARATION CHECK")
    print(
        "TIME:",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    print("#" * 80)

    # -------------------------------------------------------------------------
    # STEP 1 - Get current F_PATH
    # -------------------------------------------------------------------------

    f_path = get_dynamic_fpath()

    # Make sure the queue folders always exist.
    pending_folder = get_pending_folder(f_path)
    completed_folder = get_completed_folder(f_path)

    print()
    print("Pending folder :", pending_folder)
    print("Completed folder:", completed_folder)

    # -------------------------------------------------------------------------
    # STEP 2 - Read database
    # -------------------------------------------------------------------------

    dataframe = fetch_pending_invoice_data()

    if dataframe.empty:

        print()
        print("=" * 80)
        print("NO DATABASE DATA")
        print("=" * 80)
        print(
            "No records found where AUTO_STATUS = 0."
        )
        print(
            "NO EXCEL/CSV CREATED."
        )
        print("=" * 80)

        return None

    # -------------------------------------------------------------------------
    # STEP 3 - Find invoices already queued
    # -------------------------------------------------------------------------

    queued_invoices = get_pending_invoice_numbers(
        f_path
    )

    print()
    print(
        "Invoices already in Pending:",
        len(queued_invoices)
    )

    # -------------------------------------------------------------------------
    # STEP 4 - Remove already queued invoices
    # -------------------------------------------------------------------------

    dataframe = dataframe.copy()

    dataframe["DocNo"] = (
        dataframe["DocNo"]
        .astype(str)
        .str.strip()
    )

    new_dataframe = dataframe[
        ~dataframe["DocNo"].isin(
            queued_invoices
        )
    ].copy()

    # -------------------------------------------------------------------------
    # STEP 5 - Nothing new
    # -------------------------------------------------------------------------

    if new_dataframe.empty:

        print()
        print("=" * 80)
        print("NO NEW DATA TO EXPORT")
        print("=" * 80)
        print(
            "Database still contains AUTO_STATUS = 0 records,"
        )
        print(
            "but all of those invoices are already queued in Pending."
        )
        print(
            "NO DUPLICATE EXCEL/CSV CREATED."
        )
        print("=" * 80)

        return None

    # -------------------------------------------------------------------------
    # STEP 6 - Prepare ASN format
    # -------------------------------------------------------------------------

    asn_dataframe = prepare_asn_dataframe(
        new_dataframe
    )

    # -------------------------------------------------------------------------
    # STEP 7 - Create local staging CSV
    # -------------------------------------------------------------------------

    local_csv = create_csv(
        asn_dataframe
    )

    # -------------------------------------------------------------------------
    # STEP 8 - Copy into durable Pending queue
    # -------------------------------------------------------------------------

    pending_csv = copy_to_fpath(
        local_csv,
        f_path
    )

    document_numbers = get_document_numbers(
        new_dataframe
    )

    # -------------------------------------------------------------------------
    # IMPORTANT - DO NOT UPDATE AUTO_STATUS
    # -------------------------------------------------------------------------

    print()
    print("=" * 80)
    print("AUTO_STATUS NOT UPDATED")
    print("=" * 80)
    print(
        "The CSV is only prepared and queued."
    )
    print(
        "AUTO_STATUS will be changed to 1 "
        "ONLY after Mahindra ASN creation succeeds."
    )
    print("=" * 80)

    print()
    print("NEW PENDING FILE:", pending_csv)
    print("DOCUMENTS IN THIS FILE:")

    for doc_no in document_numbers:
        print("   ", doc_no)

    print("=" * 80)

    return pending_csv


# =============================================================================
# CONTINUOUS 20-MINUTE SCHEDULER
# =============================================================================

def run_scheduler():
    """
    Run Excel preparation independently of the HSI Automation application.

    It runs immediately once, then every 20 minutes.

    HSI Automation Start/Stop has NO effect on this scheduler.
    """

    print()
    print("#" * 80)
    print("ASN EXCEL PREPARATION SCHEDULER STARTED")
    print("#" * 80)
    print(
        "Interval:",
        CHECK_INTERVAL_SECONDS // 60,
        "minutes"
    )
    print(
        "HSI Automation application:",
        "NOT REQUIRED"
    )
    print("#" * 80)

    # First check immediately when this process starts.
    try:
        prepare_new_asn_file()
    except Exception as error:
        print()
        print("#" * 80)
        print("INITIAL ASN PREPARATION FAILED")
        print("#" * 80)
        print(
            type(error).__name__,
            ":",
            repr(error)
        )
        print("#" * 80)

    # Then repeat every 20 minutes.
    while True:

        print()
        print(
            f"Next ASN database check in "
            f"{CHECK_INTERVAL_SECONDS // 60} minutes."
        )

        time.sleep(
            CHECK_INTERVAL_SECONDS
        )

        try:
            prepare_new_asn_file()

        except Exception as error:
            # One failed cycle must not kill the scheduler.
            # The next 20-minute cycle will retry.
            print()
            print("#" * 80)
            print("ASN PREPARATION CYCLE FAILED")
            print("#" * 80)
            print(
                type(error).__name__,
                ":",
                repr(error)
            )
            print(
                "Scheduler will continue and retry "
                "on the next cycle."
            )
            print("#" * 80)


# =============================================================================
# BACKWARD-COMPATIBLE ONE-TIME MAIN
# =============================================================================

def main():

    return_code = 0

    try:

        prepare_new_asn_file()

    except KeyboardInterrupt:

        print()
        print(
            "ASN preparation cancelled by user."
        )

        return_code = 1

    except Exception as error:

        print()
        print("#" * 80)
        print("ASN PREPARATION FAILED")
        print("#" * 80)
        print(
            type(error).__name__,
            ":",
            repr(error)
        )
        print("#" * 80)

        return_code = 1

    return return_code


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":

    try:

        # Default:
        #   python excelprepare.py
        #       -> runs continuously every 20 minutes.
        #
        # Test one cycle:
        #   python excelprepare.py --once
        if "--once" in sys.argv:
            sys.exit(main())

        run_scheduler()

    except KeyboardInterrupt:

        print()
        print(
            "ASN Excel scheduler stopped by user."
        )

        sys.exit(0)

    except Exception as error:

        print()
        print("#" * 80)
        print("ASN EXCEL SCHEDULER FAILED")
        print("#" * 80)
        print(
            type(error).__name__,
            ":",
            repr(error)
        )
        print("#" * 80)

        sys.exit(1)

