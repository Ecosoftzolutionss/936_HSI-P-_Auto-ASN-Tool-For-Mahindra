"""Central, thread-safe status hub for HSI Mahindra Auto ASN."""

import re
import sys
import threading
import time
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal

MAX_HISTORY = 500


class StatusHub(QObject):
    message = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.history = []
        self.error_count = 0
        self.last_activity = time.time()
        self._lock = threading.Lock()

    def touch(self):
        self.last_activity = time.time()

    def publish(self, message, level="INFO", echo=True):
        level = str(level).upper()
        text = f"[{datetime.now():%H:%M:%S}] {message}"

        with self._lock:
            self.history.append((text, level))
            del self.history[:-MAX_HISTORY]

            if level == "ERROR":
                self.error_count += 1

            self.last_activity = time.time()

        if echo and sys.__stdout__ is not None:
            try:
                sys.__stdout__.write(f"{text} [{level}]\n")
                sys.__stdout__.flush()
            except Exception:
                pass

        self.message.emit(text, level)

    def clear(self):
        with self._lock:
            self.history.clear()
            self.error_count = 0


_hub = None


def get_hub():
    global _hub
    if _hub is None:
        _hub = StatusHub()
    return _hub


def _base(path):
    return re.split(r"[\\/]", str(path).strip())[-1]


def _safe(text):
    """Hide credentials/OTP/token values before they reach the GUI log."""
    return re.sub(
        r"(?i)(otp|password|passwd|token)\s*[:=]\s*[^\s,]+",
        r"\1=[hidden]",
        str(text),
    )


RULES = [
    (
        re.compile(r"ROWS RETURNED:\s*(\d+)", re.I),
        lambda m: (
            f"Data extracted from SQL: {m.group(1)} row(s).",
            "SUCCESS" if int(m.group(1)) else "INFO",
        ),
    ),
    (
        re.compile(r"NO DATABASE DATA", re.I),
        lambda m: ("No new data in SQL - nothing to prepare.", "INFO"),
    ),
    (
        re.compile(r"NO NEW DATA TO EXPORT", re.I),
        lambda m: ("No new data to export.", "INFO"),
    ),
    (
        re.compile(r"NO DUPLICATE EXCEL/CSV CREATED", re.I),
        lambda m: (
            "Data already exported - duplicate file not created.",
            "WARNING",
        ),
    ),
    (
        re.compile(r"ASN CSV CREATED", re.I),
        lambda m: ("Excel/CSV file prepared.", "SUCCESS"),
    ),
    (
        re.compile(r"NEW PENDING FILE:\s*(.+)", re.I),
        lambda m: (
            f"New pending ASN file ready: {_base(m.group(1))}",
            "SUCCESS",
        ),
    ),
    (
        re.compile(r"ASN PREPARATION (CYCLE )?FAILED", re.I),
        lambda m: (
            "Excel preparation failed - it will retry on the next cycle.",
            "ERROR",
        ),
    ),
    (
        re.compile(r"DATABASE CONNECTION FAILED|SOURCE DATA READ FAILED", re.I),
        lambda m: (
            "Database connection/data extraction failed.",
            "ERROR",
        ),
    ),
    (
        re.compile(r"Starting Microsoft Edge", re.I),
        lambda m: ("Opening Microsoft Edge.", "INFO"),
    ),
    (
        re.compile(r"Mahindra portal opened in external Edge", re.I),
        lambda m: ("Mahindra Supplier Portal opened.", "SUCCESS"),
    ),
    (
        re.compile(r"Microsoft login completed", re.I),
        lambda m: ("Microsoft login completed.", "SUCCESS"),
    ),
    (
        re.compile(r"Microsoft / Mahindra login failed", re.I),
        lambda m: ("Microsoft / Mahindra login failed.", "ERROR"),
    ),
    (
        re.compile(r"Windows Security popup detected", re.I),
        lambda m: (
            "Windows Security popup detected - cancelled automatically.",
            "WARNING",
        ),
    ),
    (
        re.compile(r"Mahindra OTP popup detected", re.I),
        lambda m: (
            "Mahindra requested an OTP - reading it from the mailbox.",
            "INFO",
        ),
    ),
    (
        re.compile(r"OTP RECEIVED", re.I),
        lambda m: ("OTP received from mailbox.", "SUCCESS"),
    ),
    (
        re.compile(r"MAHINDRA OTP EMAIL NOT FOUND", re.I),
        lambda m: ("OTP email was not received.", "ERROR"),
    ),
    (
        re.compile(r"Verify OTP clicked successfully", re.I),
        lambda m: ("OTP verified.", "SUCCESS"),
    ),
    (
        re.compile(r"Mahindra Dashboard detected successfully", re.I),
        lambda m: ("Mahindra dashboard opened.", "SUCCESS"),
    ),
    (
        re.compile(
            r"UPLOAD ASN PAGE OPENED SUCCESSFULLY|UPLOAD ASN PAGE VERIFIED",
            re.I,
        ),
        lambda m: ("Upload ASN page opened.", "SUCCESS"),
    ),
    (
        re.compile(r"NO PENDING ASN FILES", re.I),
        lambda m: ("No pending ASN files to upload.", "INFO"),
    ),
    (
        re.compile(r"PROCESSING OLDEST PENDING ASN FILE", re.I),
        lambda m: ("Processing the next pending ASN file.", "INFO"),
    ),
    (
        re.compile(r"ASN FILE SELECTED AND UPLOAD BUTTON CLICKED", re.I),
        lambda m: ("ASN file uploaded to Mahindra.", "INFO"),
    ),
    (
        re.compile(r"ASN creation confirmed", re.I),
        lambda m: ("ASN created on the Mahindra portal.", "SUCCESS"),
    ),
    (
        re.compile(r"Mahindra reports ASN is already created", re.I),
        lambda m: (
            "ASN already exists on the portal; validating the result rows.",
            "WARNING",
        ),
    ),
    (
        re.compile(
            r"ASN VALIDATION RESULT:\s*total=(\d+)\s+success=(\d+)\s+failed=(\d+)",
            re.I,
        ),
        lambda m: (
            f"ASN validation: {m.group(2)} successful, "
            f"{m.group(3)} failed out of {m.group(1)}.",
            "ERROR" if int(m.group(3)) else "SUCCESS",
        ),
    ),
    (
        re.compile(r"INVOICE FAILED:\s*(\S+)\s*\|\s*REASON:\s*(.+)", re.I),
        lambda m: (
            f"Invoice {m.group(1)} failed: {m.group(2)}",
            "ERROR",
        ),
    ),
    (
        re.compile(
            r"ASN BARCODE DOWNLOAD FAILED\s*(?:\|\s*REASON:\s*(.*))?",
            re.I,
        ),
        lambda m: (
            "ASN Barcode download failed"
            + (f": {m.group(1)}" if m.group(1) else "."),
            "ERROR",
        ),
    ),
    (
        re.compile(r"ASN Barcode download path is missing", re.I),
        lambda m: ("ASN Barcode path is missing in Configuration.", "ERROR"),
    ),
    (
        re.compile(r"ASN Barcode download folder is unavailable", re.I),
        lambda m: ("ASN Barcode destination folder is unavailable.", "ERROR"),
    ),
    (
        re.compile(r"Download ASN Barcode button was not found", re.I),
        lambda m: ("Mahindra Download ASN Barcode button was not found.", "ERROR"),
    ),
    (
        re.compile(r"ASN Barcode PDF download timed out", re.I),
        lambda m: ("ASN Barcode PDF download timed out.", "ERROR"),
    ),
    (
        re.compile(r"ASN BARCODE DOWNLOAD COMPLETED", re.I),
        lambda m: ("ASN Barcode PDF downloaded successfully.", "SUCCESS"),
    ),
    (
        re.compile(
            r"Cannot upload Invoice (\S+): ORIGINAL invoice PDF not found",
            re.I,
        ),
        lambda m: (
            f"Invoice {m.group(1)} failed: ORIGINAL invoice PDF not found.",
            "ERROR",
        ),
    ),
    (
        re.compile(r"DS_INVOICE_PATH is missing", re.I),
        lambda m: (
            "Invoice upload failed: DS_INVOICE_PATH is missing.",
            "ERROR",
        ),
    ),
    (
        re.compile(r"INVOICE COMPLETED:\s*(\S+)", re.I),
        lambda m: (
            f"Invoice {m.group(1)} Doc Upload completed and Auto_Status=1 verified.",
            "SUCCESS",
        ),
    ),
    (
        re.compile(r"AUTO_STATUS=1 VERIFIED for Invoice\s+(\S+)", re.I),
        lambda m: (
            f"Auto_Status=1 verified for invoice {m.group(1)}.",
            "SUCCESS",
        ),
    ),
    (
        re.compile(r"AUTO_STATUS UPDATE FAILED for Invoice\s+(\S+)", re.I),
        lambda m: (
            f"Auto_Status update failed for invoice {m.group(1)}.",
            "ERROR",
        ),
    ),
    (
        re.compile(r"PARTIAL ASN SUCCESS", re.I),
        lambda m: (
            "Partial ASN completed; failed invoices remain retryable.",
            "WARNING",
        ),
    ),
    (
        re.compile(r"QUEUE CONTINUING AFTER", re.I),
        lambda m: (
            "A failed invoice/file was isolated; the next ASN item will continue.",
            "WARNING",
        ),
    ),
    (
        re.compile(r"ASN FILE MOVED TO FAILED", re.I),
        lambda m: ("Failed ASN rows moved to Failed for retry.", "WARNING"),
    ),
    (
        re.compile(r"ASN FILE MOVED TO COMPLETED", re.I),
        lambda m: ("ASN file moved to Completed.", "SUCCESS"),
    ),
    (
        re.compile(
            r"ALL PENDING ASN FILES PROCESSED|ALL PENDING ASN INVOICES ARE COMPLETED",
            re.I,
        ),
        lambda m: ("All pending ASN work is complete.", "SUCCESS"),
    ),
    (
        re.compile(r"ASN QUEUE PROCESSING STOPPED", re.I),
        lambda m: (
            "ASN queue stopped - the current failed file remains in Pending.",
            "ERROR",
        ),
    ),
]


class ConsoleMirror:
    """
    Mirror console messages into the GUI status log.

    Unlike the old implementation, unrecognised diagnostic lines are also
    published. This is important for negative testing because the user must
    see the actual reason, not only a generic 'process failed' message.
    """

    def __init__(self, stream, hub):
        self._stream = stream
        self._hub = hub
        self._local = threading.local()
        self._last_text = None

    def write(self, data):
        data = data if isinstance(data, str) else str(data)

        if self._stream:
            try:
                self._stream.write(data)
            except Exception:
                pass

        buf = getattr(self._local, "buf", "") + data

        if "\n" in buf:
            parts = buf.split("\n")
            lines = parts[:-1]
            buf = parts[-1]

            for line in lines:
                self._handle(line)

        self._local.buf = buf if len(buf) < 10000 else ""
        return len(data)

    @staticmethod
    def _infer_level(line):
        upper = line.upper()

        if any(
            token in upper
            for token in (
                "ERROR",
                "FAILED",
                "FAILURE",
                "EXCEPTION",
                "NOT FOUND",
                "COULD NOT",
                "UNAVAILABLE",
            )
        ):
            return "ERROR"

        if any(
            token in upper
            for token in (
                "WARNING",
                "WARN",
                "PARTIAL",
                "SKIP",
                "RETRY",
            )
        ):
            return "WARNING"

        if any(
            token in upper
            for token in (
                "SUCCESS",
                "COMPLETED",
                "VERIFIED",
                "PASSED",
            )
        ):
            return "SUCCESS"

        return "INFO"

    def _handle(self, line):
        line = _safe(line.strip())

        if not line:
            return

        self._hub.touch()

        for pattern, build in RULES:
            match = pattern.search(line)

            if match:
                text, level = build(match)

                if text != self._last_text:
                    self._last_text = text
                    self._hub.publish(
                        text,
                        level,
                        echo=False,
                    )

                return

        # NEW: keep every other diagnostic line visible in Live Activity.
        if line != self._last_text:
            self._last_text = line
            self._hub.publish(
                line,
                self._infer_level(line),
                echo=False,
            )

    def flush(self):
        if self._stream:
            try:
                self._stream.flush()
            except Exception:
                pass

    def isatty(self):
        return bool(self._stream and self._stream.isatty())

    @property
    def encoding(self):
        return getattr(self._stream, "encoding", None) or "utf-8"

    def __getattr__(self, name):
        if self._stream:
            return getattr(self._stream, name)
        raise AttributeError(name)


def install_console_mirror():
    hub = get_hub()

    if not isinstance(sys.stdout, ConsoleMirror):
        sys.stdout = ConsoleMirror(sys.stdout, hub)

    if not isinstance(sys.stderr, ConsoleMirror):
        sys.stderr = ConsoleMirror(sys.stderr, hub)
