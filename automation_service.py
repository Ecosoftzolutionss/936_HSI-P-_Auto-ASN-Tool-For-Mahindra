"""
Owns the Mahindra automation (automation.AutomationController).

* Nothing here touches the GUI thread: start / stop / restart / checks all run
  on worker threads and report through the status hub.
* Every start runs pre-checks first (negative scenarios) and refuses to open
  Edge when something is missing, with a clear message per problem.
* When the controller finishes on its own, Edge is closed and the state goes
  back to Idle so the Start button works again.
"""
import os
import shutil
import threading
import time

from PyQt6.QtCore import QObject, pyqtSignal

from status_manager import get_hub

try:
    from selenium.common.exceptions import InvalidSessionIdException, WebDriverException
except Exception:
    class InvalidSessionIdException(Exception):
        pass
    class WebDriverException(Exception):
        pass

STUCK_MINUTES = 10
POLL_SECONDS = 1.0
THREAD_ATTRS = ("automation_thread", "otp_thread", "dashboard_thread")
EDGE_PATHS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)
ASN_EXTENSIONS = (".csv", ".xls", ".xlsx")


class AutomationService(QObject):
    status = pyqtSignal(str, str)           # forwarded from the hub
    running_changed = pyqtSignal(bool)

    def __init__(self, main_window=None):
        super().__init__(main_window)
        self.main_window = main_window
        self.hub = get_hub()
        self.hub.message.connect(self.status)

        self._lock = threading.RLock()
        self._controller = None
        self._thread = None
        self._running = False
        self._stop_requested = False
        self._stuck_warned = False

    # ------------------------------------------------------------------ state
    @property
    def history(self):
        return self.hub.history

    @property
    def is_running(self):
        with self._lock:
            return self._running

    def publish(self, message, level="INFO"):
        self.hub.publish(message, level)

    def _bg(self, target, name):
        threading.Thread(target=target, name=name, daemon=True).start()

    @staticmethod
    def _threads_alive(controller):
        for name in THREAD_ATTRS:
            thread = getattr(controller, name, None)
            if thread is not None and thread.is_alive():
                return True
        return False

    # ----------------------------------------------------------- pre-checks
    @staticmethod
    def _clean_path(value):
        value = str(value or "").strip().strip('"').strip("'").strip()
        return os.path.expandvars(value)

    @staticmethod
    def _edge_installed():
        return any(os.path.exists(p) for p in EDGE_PATHS) or shutil.which("msedge") is not None

    def _check_settings_row(self, row, errors, warnings, infos):
        if not row:
            errors.append(
                "No configuration is saved yet. "
                "Log in as Admin, open Configuration and save it."
            )
            return

        # Invoice/Flatfile/Portal credentials are mandatory.
        # ASN Barcode Path is optional because Barcode download is now a
        # best-effort step and must not block invoice Doc Upload processing.
        required_labels = (
            "Invoice Path",
            "Flatfile Path",
            "Portal User ID",
            "Portal Password",
        )

        required_values = (
            row[0],
            row[1],
            row[3],
            row[4],
        )

        for label, value in zip(required_labels, required_values):
            if value is None or not str(value).strip():
                errors.append(f"{label} is not configured.")

        invoice, flat, barcode = (
            self._clean_path(row[0]),
            self._clean_path(row[1]),
            self._clean_path(row[2]),
        )

        if invoice and not os.path.isdir(invoice):
            errors.append(
                f"Invoice Path folder not found: {invoice}"
            )

        if flat:
            if not os.path.isdir(flat):
                errors.append(
                    f"Flatfile Path folder not found: {flat}"
                )
            else:
                pending = os.path.join(flat, "Pending")
                count = 0

                if os.path.isdir(pending):
                    count = sum(
                        1
                        for f in os.listdir(pending)
                        if f.lower().endswith(ASN_EXTENSIONS)
                    )

                infos.append(
                    f"{count} pending ASN file(s) found."
                    if count
                    else
                    "No pending ASN files yet - the run will log in "
                    "and finish if none are prepared."
                )

        # Barcode destination is OPTIONAL. If it is unavailable, the
        # automation logs the exact reason and continues to Doc Upload.
        if barcode and os.path.isdir(barcode):
            infos.append(
                f"ASN Barcode PDF destination ready: {barcode}"
            )
        elif barcode:
            warnings.append(
                f"ASN Barcode Path folder not found: {barcode}. "
                "Barcode download will be skipped/failed safely; "
                "invoice Doc Upload will continue."
            )
        else:
            warnings.append(
                "ASN Barcode Path is not configured. "
                "Barcode download will be skipped/failed safely; "
                "invoice Doc Upload will continue."
            )

    @staticmethod
    def _check_mail_row(row, errors):
        if not row:
            errors.append("Mail (OTP) settings are not configured (Configuration > Mail / OTP).")
            return
        names = ("Mail Server", "Mail Port", "Email ID", "Email Password", "OTP Subject", "OTP Sender")
        missing = [n for n, v in zip(names, row) if v is None or not str(v).strip()]
        if missing:
            errors.append("Mail (OTP) settings incomplete: " + ", ".join(missing))

    def check_prerequisites(self):
        """Returns (errors, warnings, infos). Safe to call from any worker thread."""
        errors, warnings, infos = [], [], []
        try:
            import automation as am
        except Exception as error:
            return [f"Automation module could not be loaded: {error}"], warnings, infos

        if getattr(am, "webdriver", None) is None:
            errors.append("Selenium is not installed (pip install selenium).")
        if getattr(am, "pyautogui", None) is None:
            errors.append("pyautogui is not installed (pip install pyautogui).")
        if not self._edge_installed():
            warnings.append("Microsoft Edge was not found in its standard folders.")

        from database import get_connection
        connection = None
        try:
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute(
                "SELECT TOP 1 DS_INVOICE_PATH, F_PATH, ASN_BARCODE_PATH, PORTAL_USERID, PORTAL_PASSWORD "
                "FROM dbo.SETTINGS ORDER BY ID DESC")
            self._check_settings_row(cursor.fetchone(), errors, warnings, infos)
            cursor.execute(
                "SELECT TOP 1 MailServer, MailPort, EmailId, EmailPassword, OtpSubject, OtpSender "
                "FROM dbo.MailSettings WHERE ISNULL(IsActive, 0) = 1 ORDER BY Id DESC")
            self._check_mail_row(cursor.fetchone(), errors)
        except Exception as error:
            errors.append(f"SQL Server (settings database) is not reachable: {error}")
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

        try:
            am.AutomationController()._get_source_db_connection().close()
        except Exception as error:
            errors.append(f"Source database is not reachable: {error}")
        return errors, warnings, infos

    def _report_checks(self, errors, warnings, infos):
        for text in warnings:
            self.publish(text, "WARNING")
        for text in infos:
            self.publish(text, "INFO")
        for text in errors:
            self.publish(text, "ERROR")

    def run_prechecks(self):
        def work():
            self.publish("Running pre-checks (SQL, configuration, mail, browser)...", "INFO")
            errors, warnings, infos = self.check_prerequisites()
            self._report_checks(errors, warnings, infos)
            if errors:
                self.publish(f"Pre-checks found {len(errors)} problem(s).", "ERROR")
            else:
                self.publish("All pre-checks passed.", "SUCCESS")
        self._bg(work, "AutomationPrechecks")

    def test_database(self):
        def work():
            from database import get_connection
            try:
                connection = get_connection()
                cursor = connection.cursor()
                cursor.execute("SELECT @@SERVERNAME, DB_NAME()")
                row = cursor.fetchone()
                connection.close()
                self.publish(f"Settings database OK: {row[0]} / {row[1]}", "SUCCESS")
            except Exception as error:
                self.publish(f"Settings database connection failed: {error}", "ERROR")
            try:
                import automation as am
                am.AutomationController()._get_source_db_connection().close()
                self.publish("Source database OK.", "SUCCESS")
            except Exception as error:
                self.publish(f"Source database connection failed: {error}", "ERROR")
        self._bg(work, "DatabaseTest")

    # ---------------------------------------------------------------- start
    def start(self, reason="Start button"):
        with self._lock:
            if self._running:
                self.publish("The process is already running. Use Support Tool > Restart if it is stuck.",
                             "WARNING")
                return False
            if self._thread is not None and self._thread.is_alive():
                self.publish("The previous run is still closing - please wait a few seconds.", "WARNING")
                return False
            self._running = True
            self._stop_requested = False
            self._stuck_warned = False
            thread = threading.Thread(target=self._run, args=(reason,), name="MahindraAutomation", daemon=True)
            self._thread = thread
        self.running_changed.emit(True)
        thread.start()
        return True

    def _run(self, reason):
        controller = None
        errors_before = self.hub.error_count
        try:
            self.publish(f"Process requested from {reason}.", "INFO")
            self.publish("Running pre-checks (SQL, configuration, mail, browser)...", "INFO")
            errors, warnings, infos = self.check_prerequisites()
            self._report_checks(errors, warnings, infos)
            if errors:
                self.publish("Process NOT started. Fix the items above, then press Start again.", "ERROR")
                return
            if self._stop_requested:
                self.publish("Start cancelled.", "WARNING")
                return
            self.publish("Pre-checks passed.", "SUCCESS")

            import automation as am
            controller = am.AutomationController(
                main_window=self.main_window,
                on_back=lambda: self.publish("Automation returned to the application.", "INFO"))
            with self._lock:
                self._controller = controller

            self.publish("Starting the Mahindra automation - Microsoft Edge will open.", "INFO")
            controller.start()
            time.sleep(1.0)
            if not self._threads_alive(controller):
                self.publish("The automation did not start. Check Selenium, pyautogui and Microsoft Edge.",
                             "ERROR")
                return
            self.publish("Process started - running in the background.", "SUCCESS")
            self._monitor(controller)
        except Exception as error:
            self.publish(f"Automation failed: {error}", "ERROR")
        finally:
            self._finish(controller, errors_before)

    def _browser_is_closed(self, controller):
        """
        Detect when the user manually closes the Selenium-controlled Edge window.

        Selenium raises InvalidSessionIdException once the driver session is gone.
        Some Edge/driver versions report a generic WebDriverException instead, so
        we also inspect the exception text for an invalid/no-such-session signal.
        """
        driver = getattr(controller, "driver", None)
        if driver is None:
            return False

        try:
            # A lightweight command that fails immediately when the browser
            # session has been manually closed.
            _ = driver.current_url
            return False
        except InvalidSessionIdException:
            return True
        except WebDriverException as error:
            message = str(error).lower()
            return any(token in message for token in (
                "invalid session id",
                "no such session",
                "disconnected",
                "not connected to devtools",
                "target window already closed",
                "chrome not reachable",
                "browser window was closed",
            ))
        except Exception as error:
            message = str(error).lower()
            return any(token in message for token in (
                "invalid session id",
                "no such session",
                "disconnected",
                "target window already closed",
            ))

    def _handle_browser_closed(self, controller):
        """Turn manual Edge closure into a controlled negative-scenario result."""
        self.publish(
            "NEGATIVE SCENARIO: Microsoft Edge was closed manually by the user.",
            "ERROR",
        )
        self.publish(
            "Automation stopped because the browser session is no longer available.",
            "ERROR",
        )

        with self._lock:
            self._stop_requested = True

        # Signal the controller's own workers to stop. Do not call cleanup()
        # here because the controller worker may currently be using the driver.
        try:
            stop_event = getattr(controller, "_stop_event", None)
            if stop_event is not None:
                stop_event.set()
        except Exception:
            pass

    def _monitor(self, controller):
        idle_polls = 0
        browser_check_counter = 0

        while not self._stop_requested:
            if self._threads_alive(controller):
                idle_polls = 0
            else:
                idle_polls += 1
                if idle_polls >= 2:
                    return                          # every controller thread has ended

            # Check the Selenium session periodically. This is the important
            # negative scenario: manually closing Edge must stop the HSI run.
            browser_check_counter += 1
            if browser_check_counter >= 2:
                browser_check_counter = 0
                if self._browser_is_closed(controller):
                    self._handle_browser_closed(controller)
                    return

            idle_minutes = (time.time() - self.hub.last_activity) / 60
            if idle_minutes >= STUCK_MINUTES:
                if not self._stuck_warned:
                    self._stuck_warned = True
                    self.publish(
                        f"No activity for {int(idle_minutes)} minutes - the process may be stuck. "
                        "Use Support Tool > Restart.",
                        "WARNING",
                    )
            else:
                self._stuck_warned = False

            time.sleep(POLL_SECONDS)

    def _finish(self, controller, errors_before):
        stopped = self._stop_requested
        browser_closed = False

        if controller is not None and stopped:
            # If the stop was caused by the browser disappearing, the driver's
            # session is already gone. Avoid treating that as a normal success.
            browser_closed = self._browser_is_closed(controller)

        if controller is not None and not stopped:
            try:
                controller.cleanup()                 # close Edge so Start works again
            except Exception as error:
                self.publish(f"Browser cleanup warning: {error}", "WARNING")

        with self._lock:
            self._controller = None
            self._running = False
            self._stop_requested = False

        self.running_changed.emit(False)

        if browser_closed:
            self.publish(
                "Process stopped after the Edge browser was closed. "
                "Fix the browser/session and press Start to run again.",
                "ERROR",
            )
            return

        if controller is not None and not stopped:
            new_errors = self.hub.error_count - errors_before
            if new_errors:
                self.publish(
                    f"Process finished with {new_errors} error(s) and Edge was closed. "
                    "Check the log, then press Start to run again.",
                    "WARNING",
                )
            else:
                self.publish(
                    "Process completed. Press Start to run again.",
                    "SUCCESS",
                )

    # ------------------------------------------------------ stop / restart
    def stop(self, wait=False):
        with self._lock:
            controller = self._controller
            was_running = self._running
            self._stop_requested = True
        if controller is None and not was_running:
            self._stop_requested = False
            self.publish("No active automation process.", "WARNING")
            return
        self.publish("Stopping the Mahindra automation...", "WARNING")
        if controller is not None:
            try:
                controller.cleanup()
                self.publish("Automation stopped and Edge closed.", "SUCCESS")
            except Exception as error:
                self.publish(f"Automation stop failed: {error}", "ERROR")
        with self._lock:
            self._controller = None
            self._running = False
        self.running_changed.emit(False)
        thread = self._thread
        if wait and thread is not None and thread is not threading.current_thread() and thread.is_alive():
            thread.join(15)

    def stop_async(self):
        self._bg(lambda: self.stop(wait=True), "AutomationStop")

    def restart(self):
        self.publish("Restart requested from Support Tool.", "WARNING")

        def work():
            if self.is_running:
                self.stop(wait=True)
            deadline = time.time() + 15
            while (self._thread is not None and self._thread.is_alive()
                   and self._thread is not threading.current_thread() and time.time() < deadline):
                time.sleep(0.3)
            if not self.start("Support Tool - Restart"):
                self.publish("Restart failed - the previous run has not finished closing. "
                             "Wait a few seconds and press Start.", "ERROR")
        self._bg(work, "AutomationRestart")

    def close(self):
        if self.is_running:
            self.stop(wait=True)
