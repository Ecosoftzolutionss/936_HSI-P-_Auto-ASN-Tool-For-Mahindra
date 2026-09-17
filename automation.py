# ============================================================
# CORRECTED MAHINDRA AUTOMATION
# ============================================================
# After ASN creation:
#   1. Skip ASN Barcode PDF download.
#   2. Open Doc Upload.
#   3. Click Search.
#   4. From Date = today - 2 days.
#   5. To Date = today.
#   6. Select Material using UI5 container //*[@id="RB1-12"].
#   7. Submit using //*[@id="__button3-content"].
#   8. Click Pending Invoice using //*[@id="__button1"].
#   9. Click Pending row using //*[@id="__item2-__xmlview0--list1-0"].
#  10. Click Upload Invoice directly using idBtnIA-content / idBtnIA-BDI-content.
#      IMPORTANT: Attachment panel is already open; do NOT click Attachment again.
# ============================================================

import urllib.parse
"""
automation.py
=============
Mahindra Supplier Portal automation using a REAL Microsoft Edge window.

Flow:
    HSI Dashboard
        -> Automation
        -> Start
        -> Opens Microsoft Edge as a separate window
        -> Mahindra Supplier Portal
        -> Supplier User Login
        -> Cancel Windows Security passkey popup if it appears
        -> Read OTP from mailbox
        -> Fill OTP
        -> Verify OTP
        -> Wait for Mahindra Dashboard

IMPORTANT:
- No QWebEngineView
- No QWebEnginePage
- No embedded Mahindra portal
- Edge is controlled directly by Selenium
"""

import re
import sys
import time
import json
import email
import ctypes
import imaplib
import threading
import os
import shutil
from pathlib import Path

import pyodbc

from datetime import datetime, timezone, timedelta
from email.header import decode_header
from email.utils import parsedate_to_datetime

from database import get_connection

# Source DB contains IRPEWBInvoice / IRPEWBMulti_Part_Details.
# Settings DB contains SETTINGS / MailSettings.
try:
    from config import SOURCE_DB_DATABASE
except ImportError:
    SOURCE_DB_DATABASE = os.getenv("SOURCE_DB_DATABASE", "").strip()

try:
    from config import (
        DB_SERVER,
        DB_USERNAME,
        DB_PASSWORD,
        DB_DRIVER,
    )
except ImportError:
    DB_SERVER = os.getenv("DB_SERVER", "").strip()
    DB_USERNAME = os.getenv("DB_USERNAME", "").strip()
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server").strip()

SUPPLIER_PORTAL_URL = "https://supplier.mahindra.com/login"

# ============================================================
# OTP MAIL CONFIGURATION
# ============================================================
# IMPORTANT:
# OTP mail details are NOT read from dbo.MailSettings.
#
# They are loaded dynamically from:
#     dbo.MailSettings
#
# Mapping:
#     MailServer      -> IMAP server
#     MailPort        -> configured mail port
#     EmailId         -> mailbox username
#     EmailPassword   -> mailbox password
#     OtpSubject      -> OTP email subject
#     OtpSender       -> OTP sender
#
# The code uses IMAP4_SSL. If MailPort is stored as 995
# (POP3 SSL), 993 is used for IMAP because 995 is not an
# IMAP port. The value in the database remains unchanged.

EDGE_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0"
)

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    from selenium import webdriver
    from selenium.common.exceptions import (
        WebDriverException,
        TimeoutException,
        NoSuchElementException,
        StaleElementReferenceException,
    )
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.edge.options import Options as EdgeOptions
except ImportError:
    webdriver = None
    WebDriverException = Exception
    TimeoutException = Exception
    NoSuchElementException = Exception
    StaleElementReferenceException = Exception
    By = None
    WebDriverWait = None
    EC = None
    EdgeOptions = None


# ============================================================================
# WINDOWS SECURITY POPUP
# ============================================================================

def _find_windows_security_hwnd():
    """Find the visible native Windows Security dialog."""
    if sys.platform != "win32":
        return 0

    try:
        user32 = ctypes.windll.user32
        from ctypes import wintypes

        result = {"hwnd": 0}

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def enum_proc(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True

            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)

            if buffer.value.strip().lower() == "windows security":
                result["hwnd"] = hwnd
                return False

            return True

        user32.EnumWindows(enum_proc, 0)

        if result["hwnd"]:
            return result["hwnd"]

        return user32.FindWindowW(None, "Windows Security")

    except Exception as error:
        print("Windows Security detection error:", repr(error))
        return 0


def _cancel_windows_security(hwnd):
    """Cancel the native Windows Security/passkey dialog."""
    if not hwnd:
        return False

    try:
        user32 = ctypes.windll.user32
        from ctypes import wintypes

        cancel_hwnd = {"value": 0}

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def enum_child_proc(child_hwnd, _):
            length = user32.GetWindowTextLengthW(child_hwnd)

            if length > 0:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(child_hwnd, buffer, length + 1)

                if buffer.value.strip().lower() == "cancel":
                    cancel_hwnd["value"] = child_hwnd
                    return False

            return True

        user32.EnumChildWindows(hwnd, enum_child_proc, 0)

        # Classic Windows Security dialog.
        if cancel_hwnd["value"]:
            user32.SendMessageW(cancel_hwnd["value"], 0x00F5, 0, 0)
            print("Windows Security: Cancel clicked.")
            return True

        # Modern Windows Security dialog.
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.15)

        if pyautogui is not None:
            pyautogui.press("enter")
            print("Windows Security: Cancelled.")
            return True

        # Fallback: Escape.
        user32.PostMessageW(hwnd, 0x0100, 0x1B, 0)
        user32.PostMessageW(hwnd, 0x0101, 0x1B, 0)

        print("Windows Security: Escape sent.")
        return True

    except Exception as error:
        print("Windows Security cancel error:", repr(error))
        return False


# ============================================================================
# AUTOMATION CONTROLLER
# ============================================================================

class AutomationController:
    """
    Controls Mahindra in an external Microsoft Edge browser.

    This class intentionally does NOT create any Qt WebEngine widget.
    """

    def __init__(self, main_window=None, on_back=None):
        # Kept for compatibility with existing DashboardPage code.
        self.main_window = main_window
        self.on_back = on_back

        self.driver = None
        self.asn_barcode_download_dir = None
        # Invoice numbers detected on the Mahindra Upload ASN result page.
        # Keep them so the next step does not depend on re-reading a dynamic
        # SAP/BSP table that may disappear/re-render after ASN creation.
        self.created_asn_invoice_numbers = []

        # Current ASN queue file being processed.
        # It is moved from F_PATH/Pending -> F_PATH/Completed only after
        # Mahindra ASN creation succeeds AND Auto_Status is updated.
        self.current_asn_file_path = None

        # Handle of the Mahindra Self Service tab. It is reused between
        # multiple Pending ASN files so the queue can be processed oldest-first.
        self.self_service_window_handle = None

        self.automation_thread = None
        self.otp_thread = None
        self.dashboard_thread = None
        self.winsec_thread = None

        self._stop_event = threading.Event()
        self._running = False
        self._winsec_watcher_active = False

        self.otp_started = False
        self.otp_verify_clicked = False
        self.otp_value = None
        self.otp_wait_started = None
        self.otp_baseline_uids = set()

    # ------------------------------------------------------------------------
    # PRELOAD
    # ------------------------------------------------------------------------

    def preload(self):
        """
        Nothing is preloaded.

        Edge opens ONLY when Start is clicked.
        """
        print("Mahindra Edge preload skipped.")

    # ------------------------------------------------------------------------
    # START
    # ------------------------------------------------------------------------

    def start(self):
        """
        Start Mahindra automation in a separate Microsoft Edge window.

        Edge is opened only when Automation -> Start is clicked.
        The HSI application never embeds the Mahindra portal.
        """

        if self._running:
            print("Mahindra automation is already running.")
            self._bring_browser_to_front()
            return

        if webdriver is None or EdgeOptions is None:
            print("Selenium is not installed. Run: pip install -U selenium")
            return

        if pyautogui is None:
            print("pyautogui is not installed. Run: pip install pyautogui")
            return

        self._stop_event.clear()
        self._running = True

        self.automation_thread = threading.Thread(
            target=self._run_automation,
            daemon=True,
            name="MahindraAutomation",
        )
        self.automation_thread.start()

        print("Mahindra automation started.")

    # ------------------------------------------------------------------------
    # MAIN AUTOMATION
    # ------------------------------------------------------------------------

    def _run_automation(self):
        try:
            self._start_windows_security_watcher()

            # Open REAL Microsoft Edge.
            self._open_edge()

            if self._stop_event.is_set():
                return

            print("Mahindra portal opened in external Edge.")
            print("Current Edge URL:", self.driver.current_url)

            time.sleep(3)

            # Capture mailbox state BEFORE requesting OTP.
            self.otp_baseline_uids = self._get_mail_uids()
            self.otp_wait_started = datetime.now(timezone.utc)

            # ---------------------------------------------------------
            # SUPPLIER USER LOGIN / MICROSOFT REDIRECT
            # ---------------------------------------------------------
            # Mahindra can automatically redirect to Microsoft login.
            # In that case, there is NO "Supplier User Login" button
            # to click because the browser is already on Microsoft.
            #
            # If the Mahindra page is still visible, try the Supplier
            # User Login button. Otherwise continue directly to MS login.
            if self._is_microsoft_login_page():
                print("Microsoft login page is already open. Skipping Supplier User Login click.")
            else:
                if self._click_supplier_user_login():
                    print("Supplier User Login clicked. Waiting for Microsoft login...")
                else:
                    # The portal may be redirecting asynchronously.
                    # Wait briefly before declaring the login flow failed.
                    if self._wait_for_microsoft_login_page(20):
                        print("Mahindra automatically redirected to Microsoft login.")
                    else:
                        print("Supplier User Login could not be clicked and Microsoft login was not reached.")
                        return

            # ---------------------------------------------------------
            # MICROSOFT LOGIN
            # ---------------------------------------------------------
            if not self._perform_microsoft_login():
                print("Microsoft / Mahindra login failed.")
                return

            print("Microsoft login completed.")

            # Microsoft login has now been initiated successfully.
            self.otp_started = True

            # ---------------------------------------------------------
            # OTP / ACTIVE SESSION MODAL
            # ---------------------------------------------------------
            # Sometimes Mahindra shows:
            # "Your account is currently active on another device."
            #
            # If that modal appears, select:
            # "Switch to This Device"
            #
            # Only after that modal is closed do we wait for the OTP popup.
            time.sleep(1)

            if not self._handle_active_session_popup(timeout=25):
                print("Active-session popup was not handled. Continuing to OTP detection.")

            if not self._wait_for_otp_popup(timeout=120):
                print("Mahindra OTP popup was not detected.")
                return

            print("Mahindra OTP popup detected.")

            self._start_otp_worker()

        except Exception as error:
            print("Mahindra automation error:", repr(error))

        # Keep the controller running while Selenium is alive.
        if self.driver is None:
            self._running = False

    # ------------------------------------------------------------------------
    # OPEN REAL EDGE
    # ------------------------------------------------------------------------

    def _open_edge(self):
        """
        Open a normal, visible Microsoft Edge window.

        No QWebEngineView, QWebEnginePage, or embedded browser is used.
        Selenium controls the external Edge process.
        """

        if self.driver is not None:
            self._bring_browser_to_front()
            return

        if webdriver is None or EdgeOptions is None:
            raise RuntimeError(
                "Selenium Edge support is unavailable. "
                "Run: pip install -U selenium"
            )

        options = EdgeOptions()

        # Visible normal Edge window.
        options.add_argument("--start-maximized")
        options.add_argument("--new-window")
        options.add_argument(f"--user-agent={EDGE_USER_AGENT}")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")

        # -------------------------------------------------------------
        # DOWNLOAD DIRECTORY
        # -------------------------------------------------------------
        # ASN Barcode PDF download is intentionally skipped in the current
        # workflow. Therefore Edge startup must NOT depend on
        # ASN_BARCODE_PATH.
        #
        # F_PATH is already the configured HSI automation folder, so use it
        # as the general Edge download directory.
        f_path = self._get_asn_file_path_from_db()

        if f_path:
            download_dir = os.path.abspath(
                os.path.expandvars(
                    f_path.strip('\"').strip("'").strip()
                )
            )
        else:
            download_dir = os.path.abspath(
                os.path.join(os.getcwd(), "output")
            )

        try:
            os.makedirs(download_dir, exist_ok=True)
        except Exception as error:
            print(
                "Could not create Edge download directory:",
                repr(error),
            )
            download_dir = os.path.abspath(
                os.path.join(os.getcwd(), "output")
            )
            os.makedirs(download_dir, exist_ok=True)

        self.asn_barcode_download_dir = download_dir

        print("Edge download directory:", download_dir)

        options.add_experimental_option(
            "prefs",
            {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
            },
        )

        # IMPORTANT:
        # Do NOT add --headless.
        # Do NOT disable WebAuthn.
        # Windows Security is handled by the watcher.

        print("Starting Microsoft Edge...")

        self.driver = webdriver.Edge(options=options)
        self.driver.set_page_load_timeout(60)

        print("Microsoft Edge process created.")

        print("Opening Mahindra Supplier Portal...")

        self.driver.get(SUPPLIER_PORTAL_URL)

        try:
            self.driver.maximize_window()
        except Exception:
            pass

        print("External Edge URL:", self.driver.current_url)
        print("External Edge title:", self.driver.title)

        self._bring_browser_to_front()

    def _bring_browser_to_front(self):
        """Bring the Selenium-controlled Edge window to the foreground."""

        try:
            if self.driver is None:
                return

            self.driver.switch_to.window(
                self.driver.current_window_handle
            )

            try:
                self.driver.execute_script("window.focus();")
            except Exception:
                pass

            if sys.platform == "win32":
                try:
                    user32 = ctypes.windll.user32
                    from ctypes import wintypes

                    edge_hwnd = {"value": 0}

                    @ctypes.WINFUNCTYPE(
                        ctypes.c_bool,
                        wintypes.HWND,
                        wintypes.LPARAM,
                    )
                    def enum_proc(hwnd, _):
                        if not user32.IsWindowVisible(hwnd):
                            return True

                        length = user32.GetWindowTextLengthW(hwnd)
                        if length <= 0:
                            return True

                        buffer = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(
                            hwnd,
                            buffer,
                            length + 1,
                        )

                        title = buffer.value.strip().lower()

                        if "edge" in title:
                            edge_hwnd["value"] = hwnd
                            return False

                        return True

                    user32.EnumWindows(enum_proc, 0)

                    if edge_hwnd["value"]:
                        user32.ShowWindow(
                            edge_hwnd["value"],
                            9,
                        )
                        user32.SetForegroundWindow(
                            edge_hwnd["value"]
                        )

                except Exception as win_error:
                    print(
                        "Edge foreground warning:",
                        repr(win_error),
                    )

        except Exception as error:
            print("Could not focus Edge:", repr(error))

    # ------------------------------------------------------------------------
    # WINDOWS SECURITY WATCHER
    # ------------------------------------------------------------------------

    def _start_windows_security_watcher(self):
        if self._winsec_watcher_active:
            return

        self._winsec_watcher_active = True

        self.winsec_thread = threading.Thread(
            target=self._windows_security_loop,
            daemon=True,
            name="WindowsSecurityWatcher",
        )
        self.winsec_thread.start()

    def _stop_windows_security_watcher(self):
        self._winsec_watcher_active = False

    def _windows_security_loop(self):
        """
        Check for the REAL Windows Security window.

        We never press Enter blindly.
        Enter is sent only after the Windows Security dialog is detected.
        """

        while self._winsec_watcher_active and not self._stop_event.is_set():
            try:
                hwnd = _find_windows_security_hwnd()

                if hwnd:
                    print("Windows Security popup detected.")
                    _cancel_windows_security(hwnd)

                    # Give Windows time to close the dialog.
                    time.sleep(0.8)

            except Exception as error:
                print("Windows Security watcher error:", repr(error))

            time.sleep(0.2)

    # ------------------------------------------------------------------------
    # PORTAL CREDENTIALS
    # ------------------------------------------------------------------------

    def _get_portal_credentials(self):
        """
        Read Mahindra portal User ID and Password from dbo.SETTINGS.

        SYSTEM_NAME is intentionally NOT checked.
        The latest settings row is used.
        """
        connection = None
        cursor = None

        try:
            print("Loading portal credentials from dbo.SETTINGS...")
            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT TOP 1
                    PORTAL_USERID,
                    PORTAL_PASSWORD
                FROM dbo.SETTINGS
                ORDER BY ID DESC
                """
            )

            row = cursor.fetchone()
            if not row:
                print("No configuration found in dbo.SETTINGS.")
                return None, None

            portal_userid = str(row[0] or "").strip()
            portal_password = str(row[1] or "")

            if not portal_userid:
                print("PORTAL_USERID is empty in dbo.SETTINGS.")
                return None, None

            if not portal_password:
                print("PORTAL_PASSWORD is empty in dbo.SETTINGS.")
                return None, None

            print("Portal User ID loaded from dbo.SETTINGS.")
            return portal_userid, portal_password

        except Exception as error:
            print("Could not load Mahindra portal credentials:", repr(error))
            return None, None

        finally:
            try:
                if cursor is not None:
                    cursor.close()
            except Exception:
                pass

            try:
                if connection is not None:
                    connection.close()
            except Exception:
                pass

    # ------------------------------------------------------------------------
    # MICROSOFT LOGIN PAGE DETECTION
    # ------------------------------------------------------------------------

    def _is_microsoft_login_page(self):
        """
        Return True when the external Edge window is already on Microsoft
        login. Mahindra may redirect directly to Microsoft without showing
        a Supplier User Login button.
        """

        if self.driver is None:
            return False

        try:
            current_url = (self.driver.current_url or "").lower()

            if (
                "login.microsoftonline.com" in current_url
                or "login.microsoft.com" in current_url
            ):
                return True

            # URL can briefly remain on the Mahindra domain during a redirect,
            # so also inspect the visible page text.
            self.driver.switch_to.default_content()

            body_text = self.driver.find_element(
                By.TAG_NAME,
                "body"
            ).text.lower()

            microsoft_markers = (
                "sign in to your account",
                "enter password",
                "stay signed in",
                "don't show this again",
                "reduce the number of times"
            )

            return any(marker in body_text for marker in microsoft_markers)

        except (
            NoSuchElementException,
            StaleElementReferenceException,
            WebDriverException,
        ):
            return False
        except Exception:
            return False


    def _wait_for_microsoft_login_page(self, timeout=20):
        """
        Wait for Mahindra to redirect the external Edge window to Microsoft.
        """

        if self.driver is None:
            return False

        end_time = time.time() + timeout

        while time.time() < end_time:
            if self._stop_event.is_set():
                return False

            if self._is_microsoft_login_page():
                self._bring_browser_to_front()
                print("Microsoft login page detected:", self.driver.current_url)
                return True

            time.sleep(0.5)

        return False


    # ------------------------------------------------------------------------
    # MICROSOFT LOGIN
    # ------------------------------------------------------------------------

    def _perform_microsoft_login(self):
        """
        Automate the Microsoft login page opened by the Mahindra portal.

        Exact XPaths requested for the current page:

            User ID  : //*[@id="i0116"]
            Next     : //*[@id="idSIButton9"]
            Password : //*[@id="i0118"]
            Sign in  : //*[@id="idSIButton9"]
            Yes      : //*[@id="idSIButton9"]

        Microsoft reuses idSIButton9 on multiple steps, so every click
        is performed only after the expected page/element is available.
        """
        if self.driver is None:
            print("Microsoft login: Edge driver is not available.")
            return False

        if WebDriverWait is None or By is None or EC is None:
            print("Selenium wait support is unavailable.")
            return False

        portal_userid, portal_password = self._get_portal_credentials()

        if not portal_userid or not portal_password:
            print("Microsoft login credentials are missing.")
            return False

        userid_xpath = '//*[@id="i0116"]'
        password_xpath = '//*[@id="i0118"]'
        action_xpath = '//*[@id="idSIButton9"]'

        try:
            self.driver.switch_to.default_content()
        except Exception:
            pass

        wait = WebDriverWait(self.driver, 45)

        # -------------------------------------------------------------
        # WAIT FOR USER ID PAGE
        # -------------------------------------------------------------
        print("Waiting for Microsoft User ID field...")

        try:
            userid_element = wait.until(
                EC.visibility_of_element_located(
                    (By.XPATH, userid_xpath)
                )
            )
        except TimeoutException:
            print(
                "Microsoft User ID field was not found. Current URL:",
                self.driver.current_url,
            )
            return False

        # -------------------------------------------------------------
        # USER ID
        # -------------------------------------------------------------
        try:
            userid_element.click()
            userid_element.clear()
            userid_element.send_keys(portal_userid)
            print("Portal User ID entered.")
        except Exception as error:
            print("Unable to enter Portal User ID:", repr(error))
            return False

        # -------------------------------------------------------------
        # NEXT
        # -------------------------------------------------------------
        try:
            next_button = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, action_xpath)
                )
            )
            next_button.click()
            print("Microsoft User ID -> Next clicked.")
        except TimeoutException:
            print("Microsoft Next button was not found.")
            return False
        except Exception as error:
            print("Microsoft Next click failed:", repr(error))
            return False

        # -------------------------------------------------------------
        # PASSWORD
        # -------------------------------------------------------------
        print("Waiting for Microsoft Password field...")

        try:
            password_element = wait.until(
                EC.visibility_of_element_located(
                    (By.XPATH, password_xpath)
                )
            )
        except TimeoutException:
            print(
                "Microsoft Password field was not found. Current URL:",
                self.driver.current_url,
            )
            return False

        try:
            password_element.click()
            password_element.clear()
            password_element.send_keys(portal_password)
            print("Portal Password entered.")
        except Exception as error:
            print("Unable to enter Portal Password:", repr(error))
            return False

        # -------------------------------------------------------------
        # SIGN IN
        # -------------------------------------------------------------
        try:
            sign_in_button = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, action_xpath)
                )
            )
            sign_in_button.click()
            print("Microsoft Sign in clicked.")
        except TimeoutException:
            print("Microsoft Sign in button was not found.")
            return False
        except Exception as error:
            print("Microsoft Sign in click failed:", repr(error))
            return False

        # -------------------------------------------------------------
        # STAY SIGNED IN -> YES
        # -------------------------------------------------------------
        # Microsoft may or may not show this page depending on the
        # tenant/session. Do not blindly click idSIButton9.
        print("Checking for Microsoft 'Stay signed in?' page...")

        try:
            stay_signed_in = WebDriverWait(
                self.driver,
                15,
            ).until(
                lambda driver: self._is_stay_signed_in_page()
            )

            if stay_signed_in:
                yes_button = WebDriverWait(
                    self.driver,
                    15,
                ).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, action_xpath)
                    )
                )
                yes_button.click()
                print("Microsoft 'Stay signed in?' -> Yes clicked.")
            else:
                print("'Stay signed in?' page not required.")

        except TimeoutException:
            print(
                "'Stay signed in?' page did not appear. "
                "Continuing with the login flow."
            )
        except Exception as error:
            print(
                "Stay signed in handling warning:",
                repr(error),
            )

        # -------------------------------------------------------------
        # WAIT FOR MAHINDRA PAGE TO RETURN
        # -------------------------------------------------------------
        time.sleep(2)

        print(
            "Microsoft login step completed. Current URL:",
            self.driver.current_url,
        )

        return True

    def _is_stay_signed_in_page(self):
        """Return True only when the Microsoft Stay signed in page is visible."""
        if self.driver is None:
            return False

        try:
            body_text = self.driver.find_element(
                By.TAG_NAME,
                "body",
            ).text.lower()

            return (
                "stay signed in" in body_text
                and (
                    "don't show this again" in body_text
                    or "dont show this again" in body_text
                    or "reduce the number of times" in body_text
                )
            )
        except (
            NoSuchElementException,
            StaleElementReferenceException,
            WebDriverException,
        ):
            return False
        except Exception:
            return False

    # ------------------------------------------------------------------------
    # SUPPLIER USER LOGIN
    # ------------------------------------------------------------------------

    def _click_supplier_user_login(self):
        """
        Find and click Supplier User Login.

        Supports Angular-rendered content, common clickable elements,
        and iframe content.
        """

        if self.driver is None:
            print("Supplier login: Edge driver is not available.")
            return False

        print("Looking for Supplier User Login...")

        script = r"""
        (() => {
            const normalize = value =>
                (value || '')
                    .replace(/\s+/g, ' ')
                    .trim()
                    .toLowerCase();

            const getText = el => normalize(
                el.innerText ||
                el.textContent ||
                el.value ||
                el.getAttribute('aria-label') ||
                el.getAttribute('title') ||
                el.getAttribute('name') ||
                ''
            );

            const selector = [
                'button',
                'input',
                'a',
                '[role="button"]',
                '[role="link"]',
                'div',
                'span',
                'label'
            ].join(',');

            const elements = Array.from(
                document.querySelectorAll(selector)
            );

            const matches = elements.filter(el => {
                const text = getText(el);

                return (
                    text.includes('supplier user login') ||
                    text.includes('supplier user') ||
                    text.includes('supplier login') ||
                    text === 'supplier'
                );
            });

            if (!matches.length) {
                return {
                    ok: false,
                    reason: 'Supplier User Login element not found',
                    url: window.location.href,
                    title: document.title,
                    body: normalize(
                        document.body?.innerText || ''
                    ).substring(0, 1500)
                };
            }

            // Smallest matching element is normally the actual clickable item.
            matches.sort((a, b) =>
                getText(a).length - getText(b).length
            );

            const target = matches[0];

            target.scrollIntoView({
                behavior: 'instant',
                block: 'center',
                inline: 'center'
            });

            try {
                target.click();
            } catch (error) {
                target.dispatchEvent(
                    new MouseEvent(
                        'click',
                        {
                            bubbles: true,
                            cancelable: true,
                            view: window
                        }
                    )
                );
            }

            return {
                ok: true,
                tag: target.tagName,
                text: getText(target),
                url: window.location.href
            };
        })();
        """

        for attempt in range(1, 31):
            if self._stop_event.is_set():
                return False

            # Main document.
            try:
                self.driver.switch_to.default_content()

                result = self.driver.execute_script(script)

                print(
                    f"Supplier User Login attempt #{attempt}:",
                    result
                )

                if (
                    isinstance(result, dict)
                    and result.get("ok")
                ):
                    self.otp_started = True
                    print("Supplier User Login clicked.")
                    return True

            except Exception as error:
                print(
                    f"Supplier User Login attempt "
                    f"#{attempt} error:",
                    repr(error)
                )

            # Iframes.
            try:
                self.driver.switch_to.default_content()

                frames = self.driver.find_elements(
                    "tag name",
                    "iframe"
                )

                for index, frame in enumerate(frames):
                    try:
                        self.driver.switch_to.default_content()
                        self.driver.switch_to.frame(frame)

                        result = self.driver.execute_script(script)

                        print(
                            f"Supplier User Login iframe "
                            f"{index} attempt #{attempt}:",
                            result
                        )

                        if (
                            isinstance(result, dict)
                            and result.get("ok")
                        ):
                            self.driver.switch_to.default_content()
                            print(
                                "Supplier User Login clicked inside iframe."
                            )
                            return True

                    except Exception as frame_error:
                        print(
                            f"iframe {index} search error:",
                            repr(frame_error)
                        )

                self.driver.switch_to.default_content()

            except Exception as iframe_error:
                print(
                    "Iframe search error:",
                    repr(iframe_error)
                )

            time.sleep(1)

        # Diagnostic information.
        try:
            self.driver.switch_to.default_content()

            print(
                "Supplier login final URL:",
                self.driver.current_url
            )

            print(
                "Supplier login final title:",
                self.driver.title
            )

            body_preview = self.driver.execute_script(
                "return (document.body?.innerText || '').substring(0, 2000);"
            )

            print(
                "Supplier login page text:",
                repr(body_preview)
            )

        except Exception as error:
            print(
                "Supplier login diagnostic error:",
                repr(error)
            )

        print("Supplier User Login was not found.")
        return False

    # ------------------------------------------------------------------------
    # ACTIVE SESSION MODAL + OTP POPUP
    # ------------------------------------------------------------------------

    def _find_visible_dialog(self):
        """
        Find a visible Angular Material dialog without depending on a dynamic
        id such as mat-mdc-dialog-0, mat-mdc-dialog-1, etc.
        """
        if self.driver is None:
            return None

        dialogs = self.driver.find_elements(
            By.CSS_SELECTOR,
            "div[role='dialog'], mat-dialog-container"
        )

        for dialog in dialogs:
            try:
                if dialog.is_displayed():
                    return dialog
            except Exception:
                continue

        return None

    def _handle_active_session_popup(self, timeout=25):
        """
        Handle Mahindra's intermittent "Session Alert" popup.

        Current DOM reported by the page:
            //*[@id="mat-mdc-dialog-0"]/div/div/app-check-login-status/div

        The dialog id is dynamic, so it is NOT used for detection.

        Expected popup:
            Your account is currently active on another device.

        Expected action:
            Switch to This Device
        """
        if self.driver is None:
            return False

        print("Checking for Mahindra active-session popup...")

        end_time = time.time() + timeout
        handled = False

        while time.time() < end_time:
            if self._stop_event.is_set():
                return False

            try:
                self.driver.switch_to.default_content()

                # Stable Angular component selector. Do NOT depend on
                # mat-mdc-dialog-0 because Angular Material changes the id.
                session_components = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "app-check-login-status"
                )

                for component in session_components:
                    try:
                        if not component.is_displayed():
                            continue

                        component_text = (
                            component.text or ""
                        ).replace("\\n", " ").strip().lower()

                        if (
                            "active on another device" not in component_text
                            and "switch to this device" not in component_text
                        ):
                            continue

                        print("Mahindra active-session popup detected.")

                        # Prefer the button text. This is much safer than
                        # hard-coding button[2].
                        buttons = component.find_elements(
                            By.XPATH,
                            ".//button"
                        )

                        switch_button = None

                        for button in buttons:
                            try:
                                label = (
                                    button.text
                                    or button.get_attribute("value")
                                    or button.get_attribute("aria-label")
                                    or button.get_attribute("title")
                                    or ""
                                ).strip().lower()

                                if (
                                    "switch to this device" in label
                                    or (
                                        "switch" in label
                                        and "device" in label
                                    )
                                ):
                                    switch_button = button
                                    break
                            except Exception:
                                continue

                        # Fallback: search all buttons in the visible dialog.
                        if switch_button is None:
                            dialog = self._find_visible_dialog()

                            if dialog is not None:
                                dialog_buttons = dialog.find_elements(
                                    By.XPATH,
                                    ".//button"
                                )

                                for button in dialog_buttons:
                                    try:
                                        label = (
                                            button.text
                                            or button.get_attribute("value")
                                            or button.get_attribute("aria-label")
                                            or ""
                                        ).strip().lower()

                                        if "switch to this device" in label:
                                            switch_button = button
                                            break
                                    except Exception:
                                        continue

                        if switch_button is None:
                            print(
                                "Session Alert detected, but "
                                "'Switch to This Device' button was not found."
                            )
                            break

                        try:
                            self.driver.execute_script(
                                "arguments[0].scrollIntoView({block:'center'});",
                                switch_button,
                            )
                        except Exception:
                            pass

                        try:
                            WebDriverWait(
                                self.driver,
                                5
                            ).until(
                                lambda d, element=switch_button:
                                    element.is_displayed() and element.is_enabled()
                            )
                        except Exception:
                            pass

                        try:
                            switch_button.click()
                        except Exception:
                            # Angular Material can occasionally intercept the
                            # normal Selenium click. Use a real DOM click only
                            # as fallback.
                            self.driver.execute_script(
                                "arguments[0].click();",
                                switch_button,
                            )

                        print("Session Alert: 'Switch to This Device' clicked.")
                        handled = True

                        # Wait until the session component/dialog disappears.
                        disappear_end = time.time() + 15

                        while time.time() < disappear_end:
                            if self._stop_event.is_set():
                                return handled

                            try:
                                still_visible = False

                                current_components = self.driver.find_elements(
                                    By.CSS_SELECTOR,
                                    "app-check-login-status"
                                )

                                for current in current_components:
                                    try:
                                        if current.is_displayed():
                                            still_visible = True
                                            break
                                    except Exception:
                                        continue

                                if not still_visible:
                                    print(
                                        "Session Alert closed. "
                                        "Waiting for OTP popup..."
                                    )
                                    return handled

                            except Exception:
                                pass

                            time.sleep(0.3)

                        print(
                            "Session Alert click completed. "
                            "OTP detection will continue."
                        )
                        return handled

                    except (
                        StaleElementReferenceException,
                        NoSuchElementException,
                        WebDriverException,
                    ):
                        continue
                    except Exception as error:
                        print(
                            "Active-session popup handling warning:",
                            repr(error),
                        )

            except Exception as error:
                print(
                    "Active-session popup detection warning:",
                    repr(error),
                )

            time.sleep(0.5)

        print("No active-session popup detected.")
        return handled

    def _get_otp_component(self):
        """
        Return the visible Mahindra app-otp-input component.

        IMPORTANT:
        We intentionally use app-otp-input instead of:
            #mat-mdc-dialog-0
        because the Angular Material dialog id is dynamic.
        """
        if self.driver is None:
            return None

        components = self.driver.find_elements(
            By.CSS_SELECTOR,
            "app-otp-input"
        )

        for component in components:
            try:
                if not component.is_displayed():
                    continue

                inputs = component.find_elements(
                    By.CSS_SELECTOR,
                    "input"
                )

                visible_inputs = [
                    item
                    for item in inputs
                    if item.is_displayed()
                ]

                if len(visible_inputs) >= 6:
                    return component

            except (
                StaleElementReferenceException,
                NoSuchElementException,
            ):
                continue

        return None

    def _wait_for_otp_popup(self, timeout=120):
        """
        Wait for Mahindra's OTP popup.

        The page currently renders:
            <app-otp-input> ... six input boxes ... </app-otp-input>

        The parent Angular Material dialog id can change between runs:
            mat-mdc-dialog-0
            mat-mdc-dialog-1
            mat-mdc-dialog-2
            ...

        Therefore the dialog id is NEVER used for OTP detection.
        """
        if self.driver is None:
            return False

        print("Waiting for Mahindra OTP popup...")

        end_time = time.time() + timeout
        attempt = 0

        while time.time() < end_time:
            if self._stop_event.is_set():
                return False

            attempt += 1

            try:
                self.driver.switch_to.default_content()

                component = self._get_otp_component()

                if component is not None:
                    inputs = component.find_elements(
                        By.CSS_SELECTOR,
                        "input"
                    )

                    visible_inputs = [
                        item
                        for item in inputs
                        if item.is_displayed()
                    ]

                    print(
                        "Mahindra OTP component detected. "
                        f"Visible OTP inputs: {len(visible_inputs)}"
                    )

                    # Diagnostic only: print the current dynamic dialog id.
                    try:
                        dialog_id = self.driver.execute_script(
                            """
                            const el = arguments[0];
                            const dialog = el.closest(
                                '[role="dialog"], mat-dialog-container'
                            );
                            return dialog ? (dialog.id || '') : '';
                            """,
                            component,
                        )

                        if dialog_id:
                            print(
                                "OTP dialog detected with dynamic id:",
                                dialog_id,
                            )
                    except Exception:
                        pass

                    return True

            except (
                StaleElementReferenceException,
                NoSuchElementException,
            ):
                pass

            except WebDriverException as error:
                if attempt % 10 == 0:
                    print(
                        f"OTP popup attempt #{attempt}:",
                        repr(error),
                    )

            except Exception as error:
                if attempt % 10 == 0:
                    print(
                        f"OTP popup attempt #{attempt}:",
                        repr(error),
                    )

            # Sometimes the Session Alert appears a little after the
            # Microsoft redirect. Handle it again while waiting for OTP.
            if attempt % 4 == 0:
                try:
                    self._handle_active_session_popup(timeout=1.5)
                except Exception:
                    pass

            time.sleep(0.5)

        print("OTP popup was not detected.")
        print(
            "Stable OTP selector used:",
            "app-otp-input"
        )
        return False

    # ------------------------------------------------------------------------
    # OTP WORKER
    # ------------------------------------------------------------------------

    def _start_otp_worker(self):
        if not self.otp_started:
            print("OTP worker not started because login was not initiated.")
            return

        self.otp_thread = threading.Thread(
            target=self._otp_worker,
            daemon=True,
            name="MahindraOTPWorker",
        )
        self.otp_thread.start()

    def _otp_worker(self):
        try:
            print("=" * 70)
            print("OTP WORKER STARTED")
            print("=" * 70)

            otp = self._wait_for_new_otp_email(
                baseline_uids=set(self.otp_baseline_uids),
                timeout=110,
                poll_seconds=3,
            )

            if self._stop_event.is_set():
                return

            if not otp:
                print("=" * 70)
                print("ERROR: MAHINDRA OTP EMAIL NOT FOUND")
                print("=" * 70)
                return

            self.otp_value = str(otp).strip()

            print("=" * 70)
            print("OTP RECEIVED:", self.otp_value)
            print("=" * 70)

            success = self._fill_otp(self.otp_value)

            if success:
                print("OTP entered and Verify OTP clicked.")
            else:
                print("OTP was received but could not be filled.")

        except Exception as error:
            print("OTP worker error:", type(error).__name__, repr(error))

    # ------------------------------------------------------------------------
    # FILL OTP + VERIFY
    # ------------------------------------------------------------------------

    def _fill_otp(self, otp):
        """
        Fill Mahindra's six OTP boxes and click Verify OTP.

        The implementation does NOT depend on mat-mdc-dialog-0.
        Angular Material dialog ids are dynamic.
        """
        if self.driver is None:
            return False

        otp = str(otp).strip()

        if len(otp) != 6 or not otp.isdigit():
            print("Invalid OTP:", repr(otp))
            return False

        def get_current_otp_component():
            component = self._get_otp_component()

            if component is None:
                raise RuntimeError(
                    "Visible app-otp-input with 6 OTP boxes was not found."
                )

            return component

        def fill_current_document():
            component = WebDriverWait(
                self.driver,
                15
            ).until(
                lambda d: get_current_otp_component()
            )

            inputs = component.find_elements(
                By.CSS_SELECTOR,
                "input"
            )

            inputs = [
                item
                for item in inputs
                if item.is_displayed()
            ]

            if len(inputs) < 6:
                raise RuntimeError(
                    f"Expected at least 6 visible OTP inputs, found {len(inputs)}"
                )

            inputs = inputs[:6]

            print("Found Mahindra OTP component: app-otp-input")
            print("OTP boxes found:", len(inputs))

            # Clear existing values first.
            for input_box in inputs:
                try:
                    input_box.click()
                    input_box.clear()
                except Exception:
                    pass

            # First attempt: real keyboard events.
            for index, digit in enumerate(otp):
                # Re-find inputs because Angular can recreate them after
                # each keypress.
                component = get_current_otp_component()

                current_inputs = component.find_elements(
                    By.CSS_SELECTOR,
                    "input"
                )

                current_inputs = [
                    item
                    for item in current_inputs
                    if item.is_displayed()
                ]

                if len(current_inputs) < 6:
                    raise RuntimeError(
                        "OTP inputs changed while entering the OTP."
                    )

                input_box = current_inputs[index]

                WebDriverWait(
                    self.driver,
                    5
                ).until(
                    lambda d, element=input_box:
                        element.is_displayed() and element.is_enabled()
                )

                try:
                    input_box.click()
                except Exception:
                    pass

                try:
                    input_box.clear()
                except Exception:
                    pass

                input_box.send_keys(digit)

                time.sleep(0.12)

            # Re-read the current values.
            component = get_current_otp_component()

            inputs = component.find_elements(
                By.CSS_SELECTOR,
                "input"
            )

            inputs = [
                item
                for item in inputs
                if item.is_displayed()
            ][:6]

            values = []

            for input_box in inputs:
                try:
                    values.append(
                        str(
                            input_box.get_attribute("value") or ""
                        )
                    )
                except Exception:
                    values.append("")

            entered = "".join(values)

            print("OTP boxes after keyboard entry:", repr(entered))

            # Angular-compatible fallback.
            if entered != otp:
                print(
                    "Keyboard entry did not populate the OTP completely. "
                    "Using Angular-compatible JS events."
                )

                js = """
                const otp = arguments[0];

                const component = document.querySelector(
                    'app-otp-input'
                );

                if (!component) {
                    return '';
                }

                const inputs = Array.from(
                    component.querySelectorAll('input')
                ).filter(
                    input => {
                        const style = window.getComputedStyle(input);
                        return (
                            style.display !== 'none' &&
                            style.visibility !== 'hidden' &&
                            input.offsetParent !== null
                        );
                    }
                ).slice(0, 6);

                inputs.forEach((input, index) => {
                    const value = otp[index] || '';

                    input.focus();

                    const setter =
                        Object.getOwnPropertyDescriptor(
                            HTMLInputElement.prototype,
                            'value'
                        );

                    if (setter && setter.set) {
                        setter.set.call(input, value);
                    } else {
                        input.value = value;
                    }

                    input.dispatchEvent(
                        new InputEvent(
                            'input',
                            {
                                bubbles: true,
                                inputType: 'insertText',
                                data: value
                            }
                        )
                    );

                    input.dispatchEvent(
                        new Event(
                            'change',
                            { bubbles: true }
                        )
                    );

                    input.blur();
                });

                return inputs
                    .map(input => input.value || '')
                    .join('');
                """

                entered = self.driver.execute_script(
                    js,
                    otp,
                )

                print(
                    "OTP boxes after JS entry:",
                    repr(entered),
                )

            if entered != otp:
                # Last fallback: enter the complete OTP into the first box.
                # Some Angular OTP controls listen for a paste/input sequence
                # and automatically distribute the digits.
                print(
                    "OTP value still does not match. "
                    "Trying complete OTP through the first visible box."
                )

                component = get_current_otp_component()

                inputs = component.find_elements(
                    By.CSS_SELECTOR,
                    "input"
                )

                inputs = [
                    item
                    for item in inputs
                    if item.is_displayed()
                ]

                if len(inputs) >= 6:
                    first = inputs[0]

                    try:
                        first.click()
                        first.clear()
                    except Exception:
                        pass

                    first.send_keys(otp)
                    time.sleep(0.5)

                component = get_current_otp_component()

                inputs = component.find_elements(
                    By.CSS_SELECTOR,
                    "input"
                )

                inputs = [
                    item
                    for item in inputs
                    if item.is_displayed()
                ][:6]

                entered = "".join(
                    str(
                        item.get_attribute("value") or ""
                    )
                    for item in inputs
                )

                print(
                    "OTP boxes after complete-value fallback:",
                    repr(entered),
                )

            if entered != otp:
                print(
                    "OTP value mismatch. Expected:",
                    otp,
                    "Actual:",
                    entered,
                )
                return False

            # -------------------------------------------------------------
            # FIND VERIFY OTP BUTTON
            # -------------------------------------------------------------
            #
            # Do not use:
            #     #mat-mdc-dialog-0
            #
            # Instead find the dialog containing app-otp-input, then find
            # the button whose visible label is "Verify OTP".
            #
            component = get_current_otp_component()

            dialog = self.driver.execute_script(
                """
                const component = arguments[0];
                return component.closest(
                    '[role="dialog"], mat-dialog-container'
                );
                """,
                component,
            )

            if dialog is None:
                raise RuntimeError(
                    "Could not find the Angular Material dialog "
                    "containing app-otp-input."
                )

            verify_candidates = dialog.find_elements(
                By.XPATH,
                ".//button | .//*[@role='button'] | "
                ".//input[@type='button'] | .//input[@type='submit']"
            )

            verify_button = None

            for button in verify_candidates:
                try:
                    label = (
                        button.text
                        or button.get_attribute("value")
                        or button.get_attribute("aria-label")
                        or button.get_attribute("title")
                        or ""
                    ).strip().lower()

                    if "verify otp" in label:
                        verify_button = button
                        break

                except (
                    StaleElementReferenceException,
                    NoSuchElementException,
                ):
                    continue

            if verify_button is None:
                # Global fallback, still based on visible button text.
                all_buttons = self.driver.find_elements(
                    By.XPATH,
                    "//button | //*[@role='button']"
                )

                for button in all_buttons:
                    try:
                        if not button.is_displayed():
                            continue

                        label = (
                            button.text
                            or button.get_attribute("value")
                            or button.get_attribute("aria-label")
                            or ""
                        ).strip().lower()

                        if "verify otp" in label:
                            verify_button = button
                            break

                    except Exception:
                        continue

            if verify_button is None:
                raise RuntimeError(
                    "Verify OTP button was not found."
                )

            WebDriverWait(
                self.driver,
                10
            ).until(
                lambda d:
                    verify_button.is_displayed()
                    and verify_button.is_enabled()
            )

            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});",
                    verify_button,
                )
            except Exception:
                pass

            time.sleep(0.2)

            try:
                verify_button.click()
            except Exception:
                self.driver.execute_script(
                    "arguments[0].click();",
                    verify_button,
                )

            print("Verify OTP clicked successfully.")
            return True

        # Main document.
        try:
            self.driver.switch_to.default_content()

            if fill_current_document():
                self.otp_verify_clicked = True
                print(
                    "OTP verified. "
                    "Waiting for Mahindra Dashboard."
                )
                self._start_dashboard_poll()
                return True

        except Exception as error:
            print(
                "OTP fill in main document failed:",
                repr(error)
            )

        # Iframe fallback.
        try:
            self.driver.switch_to.default_content()

            frames = self.driver.find_elements(
                By.TAG_NAME,
                "iframe"
            )

            for index, frame in enumerate(frames):
                try:
                    self.driver.switch_to.default_content()
                    self.driver.switch_to.frame(frame)

                    if fill_current_document():
                        self.driver.switch_to.default_content()

                        self.otp_verify_clicked = True

                        print(
                            f"OTP verified inside iframe {index}. "
                            "Waiting for Mahindra Dashboard."
                        )

                        self._start_dashboard_poll()
                        return True

                except Exception as frame_error:
                    print(
                        f"OTP iframe {index} fill failed:",
                        repr(frame_error)
                    )

            self.driver.switch_to.default_content()

        except Exception as iframe_error:
            print(
                "OTP iframe processing failed:",
                repr(iframe_error)
            )

        return False

    # ------------------------------------------------------------------------
    # DASHBOARD DETECTION
    # ------------------------------------------------------------------------

    def _start_dashboard_poll(self):
        self.dashboard_thread = threading.Thread(
            target=self._dashboard_loop,
            daemon=True,
            name="MahindraDashboardWatcher",
        )
        self.dashboard_thread.start()

    def _dashboard_loop(self):
        """
        Wait for the Mahindra dashboard after OTP verification.

        IMPORTANT:
        The dashboard is a normal Angular page and the URL itself is a stable
        indicator (currently /dashboard). Do not rely only on JavaScript
        execution or page body text because Angular can still be rendering
        while the URL has already changed.
        """
        print("Mahindra Dashboard watcher started.")

        timeout_seconds = 180
        started = time.time()

        while time.time() - started < timeout_seconds:
            if self._stop_event.is_set() or self.driver is None:
                print("Dashboard watcher stopped.")
                return

            try:
                # Always switch back to the main document.
                self.driver.switch_to.default_content()

                current_url = (self.driver.current_url or "").strip()
                current_url_lower = current_url.lower()

                try:
                    title = (self.driver.title or "").strip()
                except Exception:
                    title = ""

                try:
                    body_text = (
                        self.driver.find_element(By.TAG_NAME, "body").text or ""
                    ).strip().lower()
                except Exception:
                    body_text = ""

                # URL is the PRIMARY dashboard check.
                url_ready = "/dashboard" in current_url_lower

                # Angular dashboard can be identified by these visible labels
                # even if the URL is temporarily different during navigation.
                page_ready = (
                    "my business" in body_text
                    or "oe supplies" in body_text
                    or "supplier dashboard" in body_text
                )

                print(
                    "Dashboard check | "
                    f"URL: {current_url} | "
                    f"Title: {title} | "
                    f"URLReady: {url_ready} | "
                    f"PageReady: {page_ready}"
                )

                if url_ready or page_ready:
                    print("Mahindra Dashboard detected successfully.")
                    print("Dashboard URL:", current_url)

                    # Give Angular a moment to finish rendering the dashboard
                    # cards before trying to click OE Supplies.
                    time.sleep(2)
                    self._bring_browser_to_front()

                    print("Starting automatic navigation to Upload ASN...")
                    navigation_success = self._navigate_to_upload_asn()

                    if navigation_success:
                        print("=" * 70)
                        print("MAHINDRA UPLOAD ASN PAGE OPENED SUCCESSFULLY")
                        print("=" * 70)
                    else:
                        print("=" * 70)
                        print("MAHINDRA UPLOAD ASN NAVIGATION FAILED")
                        print("Dashboard is open. You can inspect the page in Edge.")
                        print("=" * 70)

                    return

            except (
                StaleElementReferenceException,
                NoSuchElementException,
            ) as error:
                print("Dashboard DOM changed; retrying:", repr(error))

            except WebDriverException as error:
                print("Dashboard WebDriver check warning:", repr(error))

            except Exception as error:
                print("Dashboard detection error:", repr(error))

            time.sleep(0.7)

        print("Mahindra Dashboard detection timed out after", timeout_seconds, "seconds.")
        try:
            print("Last known Edge URL:", self.driver.current_url if self.driver else "No driver")
        except Exception:
            pass

    # ------------------------------------------------------------------------
    # OE SUPPLIES -> TRANSACTIONS -> SELF SERVICE -> UPLOAD ASN
    # ------------------------------------------------------------------------

    def _click_element_with_fallbacks(
        self,
        description,
        selectors,
        timeout=20,
        post_click_wait=1.0,
    ):
        """
        Click the first visible/enabled element matching one of the supplied
        Selenium locators.

        Angular Material can generate dynamic ids, so stable text/attributes
        are preferred and the user-provided XPaths are retained as fallbacks.
        """
        if self.driver is None:
            return False

        end_time = time.time() + timeout
        last_error = None

        while time.time() < end_time:
            if self._stop_event.is_set():
                return False

            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass

            for by, selector in selectors:
                try:
                    elements = self.driver.find_elements(by, selector)

                    for element in elements:
                        try:
                            if not element.is_displayed():
                                continue

                            try:
                                self.driver.execute_script(
                                    """
                                    arguments[0].scrollIntoView({
                                        behavior: 'instant',
                                        block: 'center',
                                        inline: 'center'
                                    });
                                    """,
                                    element,
                                )
                            except Exception:
                                pass

                            try:
                                WebDriverWait(
                                    self.driver,
                                    3,
                                ).until(
                                    lambda d, el=element:
                                        el.is_displayed()
                                        and el.is_enabled()
                                )
                            except Exception:
                                pass

                            try:
                                element.click()
                            except Exception:
                                self.driver.execute_script(
                                    "arguments[0].click();",
                                    element,
                                )

                            print(
                                f"{description} clicked using "
                                f"{by} -> {selector}"
                            )

                            if post_click_wait > 0:
                                time.sleep(post_click_wait)

                            return True

                        except (
                            StaleElementReferenceException,
                            NoSuchElementException,
                        ) as error:
                            last_error = error
                            continue

                        except Exception as error:
                            last_error = error
                            continue

                except Exception as error:
                    last_error = error
                    continue

            time.sleep(0.4)

        print(
            f"{description} was not found/clicked. "
            f"Last error: {repr(last_error)}"
        )
        return False

    def _wait_for_element_with_fallbacks(
        self,
        description,
        selectors,
        timeout=20,
    ):
        """
        Wait for any visible element matching the supplied locators.
        """
        if self.driver is None:
            return None

        end_time = time.time() + timeout

        while time.time() < end_time:
            if self._stop_event.is_set():
                return None

            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass

            for by, selector in selectors:
                try:
                    elements = self.driver.find_elements(by, selector)

                    for element in elements:
                        try:
                            if element.is_displayed():
                                print(
                                    f"{description} detected using "
                                    f"{by} -> {selector}"
                                )
                                return element
                        except (
                            StaleElementReferenceException,
                            NoSuchElementException,
                        ):
                            continue

                except Exception:
                    continue

            time.sleep(0.4)

        print(f"{description} was not detected.")
        return None

    def _click_text_in_visible_page(
        self,
        text_value,
        description,
        timeout=15,
    ):
        """
        Generic text-based click fallback for Angular-rendered controls.
        """
        if self.driver is None:
            return False

        normalized = text_value.strip().lower()
        end_time = time.time() + timeout

        while time.time() < end_time:
            if self._stop_event.is_set():
                return False

            try:
                self.driver.switch_to.default_content()

                elements = self.driver.find_elements(
                    By.XPATH,
                    (
                        "//*[self::button or self::a or self::div or "
                        "self::span or self::mat-list-item or "
                        "@role='tab' or @role='button']"
                    ),
                )

                candidates = []

                for element in elements:
                    try:
                        if not element.is_displayed():
                            continue

                        element_text = (
                            element.text
                            or element.get_attribute("aria-label")
                            or element.get_attribute("title")
                            or ""
                        ).strip().lower()

                        if element_text == normalized:
                            candidates.append(element)

                    except (
                        StaleElementReferenceException,
                        NoSuchElementException,
                    ):
                        continue

                candidates.sort(
                    key=lambda el: len(
                        (
                            el.text
                            or el.get_attribute("aria-label")
                            or ""
                        )
                    )
                )

                for element in candidates:
                    try:
                        self.driver.execute_script(
                            """
                            arguments[0].scrollIntoView({
                                behavior: 'instant',
                                block: 'center'
                            });
                            """,
                            element,
                        )

                        try:
                            element.click()
                        except Exception:
                            self.driver.execute_script(
                                "arguments[0].click();",
                                element,
                            )

                        print(
                            f"{description} clicked using text: "
                            f"{text_value}"
                        )
                        time.sleep(1)
                        return True

                    except Exception:
                        continue

            except Exception as error:
                print(
                    f"{description} text click warning:",
                    repr(error),
                )

            time.sleep(0.4)

        print(
            f"{description} could not be clicked using text: "
            f"{text_value}"
        )
        return False

    def _switch_to_new_or_changed_window(self, old_handles=None, timeout=15):
        """Switch to the Edge tab/window opened by the Mahindra portal."""
        if self.driver is None:
            return False

        old_handles = set(old_handles or [])
        end_time = time.time() + timeout

        while time.time() < end_time:
            if self._stop_event.is_set():
                return False

            try:
                handles = self.driver.window_handles

                # Prefer a newly created tab/window.
                new_handles = [h for h in handles if h not in old_handles]
                if new_handles:
                    self.driver.switch_to.window(new_handles[-1])
                    print("Switched to newly opened Edge tab/window:", self.driver.current_url)
                    return True

                # If no new handle was created, check all existing handles for
                # the Mahindra SAP / Self-Service page.
                for handle in reversed(handles):
                    try:
                        self.driver.switch_to.window(handle)
                        url = (self.driver.current_url or "").lower()
                        title = (self.driver.title or "").lower()

                        if (
                            "srmapps.mahindra.com" in url
                            or "supplier self-services" in title
                            or "self-services" in title
                            or "sap" in url
                        ):
                            print("Switched to Mahindra Self Service tab:", self.driver.current_url)
                            return True
                    except Exception:
                        continue

            except Exception as error:
                print("Window/tab switch warning:", repr(error))

            time.sleep(0.5)

        return False

    def _find_upload_asn_href(self, timeout=20):
        """
        Find the real Mahindra Upload ASN URL from the Self Service page.

        The portal renders:
            <a id="start_Upload" ... target="_blank">Upload ASN</a>

        If Selenium cannot return the element, use JavaScript to read the
        href directly from the page. This also avoids depending on a stale
        WebElement.
        """
        if self.driver is None:
            return None

        end_time = time.time() + timeout

        while time.time() < end_time:
            if self._stop_event.is_set():
                return None

            try:
                self.driver.switch_to.default_content()

                result = self.driver.execute_script(
                    """
                    const exact = document.getElementById('start_Upload');

                    if (exact) {
                        return {
                            found: true,
                            href: exact.href || exact.getAttribute('href') || '',
                            text: (exact.innerText || '').trim()
                        };
                    }

                    const links = Array.from(document.querySelectorAll('a'));

                    const upload = links.find(a => {
                        const text = (a.innerText || '').trim().toLowerCase();
                        const href = (a.getAttribute('href') || '').toLowerCase();

                        return (
                            text === 'upload asn' ||
                            href.includes('zasnupload') ||
                            href.includes('upload.htm')
                        );
                    });

                    if (upload) {
                        return {
                            found: true,
                            href: upload.href || upload.getAttribute('href') || '',
                            text: (upload.innerText || '').trim()
                        };
                    }

                    return {
                        found: false,
                        href: '',
                        text: ''
                    };
                    """
                )

                if result and result.get("found"):
                    href = (result.get("href") or "").strip()

                    if href:
                        print("Upload ASN href found:", href)
                        return href

            except Exception as error:
                print("Upload ASN href search warning:", repr(error))

            time.sleep(0.5)

        return None


    def _open_upload_asn_in_new_tab(self, timeout=20):
        """
        Open Mahindra Upload ASN in a NEW Edge tab.

        Priority:
          1. Exact //*[@id="start_Upload"] href
          2. Any Upload ASN / zasnupload href in the current page
          3. Known Mahindra relative BSP path:
                ../zasnupload/upload.htm

        This is intentional because the DOM shows target="_blank".
        """
        if self.driver is None:
            return False

        old_handles = set(self.driver.window_handles)

        # -------------------------------------------------------------
        # A. Try the exact element first.
        # -------------------------------------------------------------
        href = self._find_upload_asn_href(timeout=timeout)

        # -------------------------------------------------------------
        # B. If href was not found, build the same relative BSP URL.
        # -------------------------------------------------------------
        if not href:
            try:
                current_url = self.driver.current_url or ""

                if current_url:
                    href = urllib.parse.urljoin(
                        current_url,
                        "../zasnupload/upload.htm",
                    )

                    print(
                        "Upload ASN element was not readable. "
                        "Using Mahindra relative Upload ASN URL:",
                        href,
                    )
            except Exception as error:
                print(
                    "Could not build Upload ASN URL:",
                    repr(error),
                )

        if not href:
            print("Upload ASN URL could not be determined.")
            return False

        # -------------------------------------------------------------
        # C. Open the upload page explicitly in a NEW TAB.
        # -------------------------------------------------------------
        try:
            self.driver.execute_script(
                "window.open(arguments[0], '_blank');",
                href,
            )
        except Exception as error:
            print(
                "window.open for Upload ASN failed:",
                repr(error),
            )
            return False

        # -------------------------------------------------------------
        # D. Switch to the newly-created tab.
        # -------------------------------------------------------------
        end_time = time.time() + timeout

        while time.time() < end_time:
            if self._stop_event.is_set():
                return False

            try:
                handles = list(self.driver.window_handles)
                new_handles = [
                    h for h in handles
                    if h not in old_handles
                ]

                if new_handles:
                    new_handle = new_handles[-1]
                    self.driver.switch_to.window(new_handle)

                    print(
                        "UPLOAD ASN NEW TAB OPENED:",
                        self.driver.current_url,
                    )

                    # Give the SAP/BSP page time to load.
                    try:
                        WebDriverWait(
                            self.driver,
                            min(15, timeout),
                        ).until(
                            lambda d: d.execute_script(
                                "return document.readyState"
                            ) in ("interactive", "complete")
                        )
                    except Exception:
                        pass

                    return True

            except Exception as error:
                print(
                    "Waiting for Upload ASN new tab warning:",
                    repr(error),
                )

            time.sleep(0.4)

        print("Upload ASN new tab was not created.")
        return False


    def _navigate_to_upload_asn(self, timeout_per_step=25):
        """
        Complete the Mahindra navigation and process the ASN queue.

        Flow:
            Dashboard
                -> OE Supplies
                -> TRANSACTIONS
                -> Transaction Sub Menu
                -> Self Service
                -> Open Upload ASN in a NEW TAB
                -> Process the oldest Pending ASN file

        IMPORTANT:
        Self Service opens the SAP/BSP page in another Edge tab. The first
        ASN must also explicitly open the Upload ASN page. Previously this
        happened only when processed_any was True, which caused the first ASN
        to remain on srmsus/default.htm and fail Upload ASN verification.
        """
        if self.driver is None:
            print("Upload ASN navigation: Edge driver unavailable.")
            return False

        self.created_asn_invoice_numbers = []
        self.current_asn_file_path = None

        print("=" * 70)
        print("STARTING MAHINDRA OE SUPPLIES -> UPLOAD ASN NAVIGATION")
        print("=" * 70)

        try:
            self.driver.switch_to.default_content()
            self._bring_browser_to_front()
        except Exception:
            pass

        # -------------------------------------------------------------
        # STEP 1: OE SUPPLIES
        # -------------------------------------------------------------
        print("STEP 1: Looking for OE Supplies...")

        oe_supplies_selectors = [
            (
                By.XPATH,
                '//*[@id="sidenavContainer"]/mat-sidenav-content/'
                'app-dashboard/div/div[1]/div[2]/div/div[2]/div/div/'
                'div[1]/div[1]',
            ),
            (By.XPATH, "//*[normalize-space()='OE Supplies']"),
        ]

        if not self._click_element_with_fallbacks(
            "OE Supplies",
            oe_supplies_selectors,
            timeout=timeout_per_step,
            post_click_wait=1.5,
        ):
            if not self._click_text_in_visible_page(
                "OE Supplies", "OE Supplies", timeout=8
            ):
                return False

        self._wait_for_element_with_fallbacks(
            "OE Supplies page",
            [
                (By.CSS_SELECTOR, "app-oesupplies"),
                (By.XPATH, "//app-oesupplies"),
            ],
            timeout=timeout_per_step,
        )

        # -------------------------------------------------------------
        # STEP 2: TRANSACTIONS TAB
        # -------------------------------------------------------------
        print("STEP 2: Looking for TRANSACTIONS tab...")

        transaction_tab_selectors = [
            (By.XPATH, '//*[@id="mat-tab-label-2-1"]/span[2]/span'),
            (
                By.XPATH,
                "//div[@role='tab'][.//span[normalize-space()='TRANSACTIONS']]",
            ),
            (
                By.XPATH,
                "//*[@role='tab'][contains("
                "translate(normalize-space(.), "
                "'abcdefghijklmnopqrstuvwxyz', "
                "'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), "
                "'TRANSACTIONS')]",
            ),
            (By.XPATH, "//*[normalize-space()='TRANSACTIONS']"),
        ]

        if not self._click_element_with_fallbacks(
            "TRANSACTIONS tab",
            transaction_tab_selectors,
            timeout=timeout_per_step,
            post_click_wait=1.2,
        ):
            if not self._click_text_in_visible_page(
                "TRANSACTIONS", "TRANSACTIONS tab", timeout=8
            ):
                return False

        # -------------------------------------------------------------
        # STEP 3: TRANSACTION SUB MENU
        # -------------------------------------------------------------
        print("STEP 3: Opening Transaction sub menu...")

        transaction_submenu_selectors = [
            (
                By.XPATH,
                '//*[@id="sidenavContainer"]/mat-sidenav-content/'
                'app-oesupplies/div/div/div[2]/mat-card/div',
            ),
            (By.XPATH, "//app-oesupplies//mat-card"),
            (By.CSS_SELECTOR, "app-oesupplies mat-card"),
        ]

        submenu_opened = self._click_element_with_fallbacks(
            "Transaction sub menu",
            transaction_submenu_selectors,
            timeout=timeout_per_step,
            post_click_wait=1.0,
        )

        if not submenu_opened:
            print(
                "Transaction sub menu trigger was not clicked. "
                "Checking whether the transaction menu is already visible."
            )

        self._wait_for_element_with_fallbacks(
            "Transaction menu list",
            [
                (
                    By.XPATH,
                    '//*[@id="sidenavContainer"]/mat-sidenav-content/'
                    'app-oesupplies/div/div/div[2]/mat-card/div/div',
                ),
                (By.CSS_SELECTOR, "app-oesupplies mat-list"),
                (By.XPATH, "//app-oesupplies//mat-list"),
            ],
            timeout=10,
        )

        # -------------------------------------------------------------
        # STEP 4: SELF SERVICE
        # -------------------------------------------------------------
        print("STEP 4: Looking for Self Service...")

        self_service_selectors = [
            (
                By.XPATH,
                '//*[@id="sidenavContainer"]/mat-sidenav-content/'
                'app-oesupplies/div/div/div[2]/mat-card/div/div/'
                'mat-list/mat-list-item[1]',
            ),
            (
                By.XPATH,
                "//app-oesupplies//mat-list-item["
                "contains(translate(normalize-space(.), "
                "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
                "'abcdefghijklmnopqrstuvwxyz'), "
                "'self service')]",
            ),
            (
                By.XPATH,
                "//mat-list-item["
                "contains(translate(normalize-space(.), "
                "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
                "'abcdefghijklmnopqrstuvwxyz'), "
                "'self service')]",
            ),
        ]

        handles_before_self_service = set(self.driver.window_handles)

        if not self._click_element_with_fallbacks(
            "Self Service",
            self_service_selectors,
            timeout=timeout_per_step,
            post_click_wait=1.5,
        ):
            if not self._click_text_in_visible_page(
                "Self Service", "Self Service", timeout=8
            ):
                return False

        print("Self Service clicked. Checking for new Mahindra SAP tab...")

        switched = self._switch_to_new_or_changed_window(
            handles_before_self_service,
            timeout=20,
        )

        if not switched:
            print(
                "Self Service did not create/change an Edge tab. "
                "Continuing with the current tab."
            )

        try:
            self.driver.switch_to.default_content()
            print("Current Self Service URL:", self.driver.current_url)
            print("Current Self Service title:", self.driver.title)
        except Exception:
            pass

        # Save the Self Service tab before opening Upload ASN.
        try:
            self.self_service_window_handle = (
                self.driver.current_window_handle
            )
            print(
                "Self Service window handle saved:",
                self.self_service_window_handle,
            )
        except Exception as error:
            print(
                "Could not save Self Service window handle:",
                repr(error),
            )
            return False

        # -------------------------------------------------------------
        # STEP 5: ASN QUEUE
        # -------------------------------------------------------------
        f_path = self._get_asn_file_path_from_db()

        if not f_path:
            print("ASN queue cannot start because F_PATH is unavailable.")
            return False

        pending_files = self._get_pending_asn_files(f_path)

        if not pending_files:
            print("=" * 70)
            print("NO PENDING ASN FILES")
            print("=" * 70)
            print("Excel preparation may not have found new DB data yet.")
            print("No ASN upload will be attempted.")
            print("=" * 70)
            return True

        # -------------------------------------------------------------
        # IMPORTANT FIX FOR FIRST ASN
        # -------------------------------------------------------------
        # The current tab is Self Service. _process_current_asn_upload_page()
        # expects the Upload ASN page. Therefore ALWAYS open Upload ASN before
        # the first queue iteration, not only after the first ASN is processed.
        # -------------------------------------------------------------
        print("=" * 70)
        print("OPENING UPLOAD ASN FOR FIRST PENDING FILE")
        print("=" * 70)

        if not self._open_upload_asn_in_new_tab(timeout=20):
            print("=" * 70)
            print("COULD NOT OPEN UPLOAD ASN PAGE")
            print("The current ASN file remains in Pending.")
            print("=" * 70)
            return False

        try:
            self.driver.switch_to.default_content()
            print("Upload ASN tab URL:", self.driver.current_url)
            print("Upload ASN tab title:", self.driver.title)
        except Exception:
            pass

        processed_any = False

        while not self._stop_event.is_set():
            # ---------------------------------------------------------
            # SECOND ASN AND ONWARD
            # ---------------------------------------------------------
            # After successful processing, Doc Upload may have opened another
            # tab. Return to Self Service and open a fresh Upload ASN tab.
            # ---------------------------------------------------------
            if processed_any:
                if not self._switch_to_self_service_tab(timeout=20):
                    print(
                        "Could not return to Mahindra Self Service "
                        "for the next ASN file."
                    )
                    return False

                try:
                    self.self_service_window_handle = (
                        self.driver.current_window_handle
                    )
                except Exception:
                    pass

                if not self._open_upload_asn_in_new_tab(timeout=20):
                    print(
                        "Could not open Upload ASN for the next Pending file."
                    )
                    return False

            # ---------------------------------------------------------
            # Process exactly ONE oldest Pending file.
            # ---------------------------------------------------------
            print("=" * 70)
            print("PROCESSING OLDEST PENDING ASN FILE")
            print("FILE:", os.path.basename(pending_files[0]))
            print("=" * 70)

            result = self._process_current_asn_upload_page(timeout=60)

            if not result:
                print("=" * 70)
                print("ASN QUEUE PROCESSING STOPPED")
                print("The failed/current file remains in Pending.")
                print("=" * 70)
                return False

            processed_any = True

            # ---------------------------------------------------------
            # Check whether another Pending file exists.
            # ---------------------------------------------------------
            f_path = self._get_asn_file_path_from_db()

            if not f_path:
                print("F_PATH is no longer available.")
                return False

            pending_files = self._get_pending_asn_files(f_path)

            if not pending_files:
                print("=" * 70)
                print("ALL PENDING ASN FILES PROCESSED")
                print("=" * 70)
                return True

            print("=" * 70)
            print(
                "NEXT PENDING ASN FILE:",
                os.path.basename(pending_files[0]),
            )
            print("REMAINING PENDING FILES:", len(pending_files))
            print("=" * 70)

        return False

    # ------------------------------------------------------------------------
    # ASN QUEUE - FIND PENDING FILES
    # ------------------------------------------------------------------------

    def _get_pending_asn_files(self, folder_path):
        """
        Return ASN files from F_PATH/Pending in oldest-first order.

        Only CSV/XLS/XLSX files are considered. CSV is preferred because
        Mahindra Upload ASN expects CSV.
        """

        if not folder_path:
            return []

        pending_folder = os.path.join(
            folder_path,
            "Pending",
        )

        if not os.path.isdir(pending_folder):
            print(
                "ASN Pending folder does not exist:",
                pending_folder,
            )
            return []

        allowed_extensions = (
            ".csv",
            ".xls",
            ".xlsx",
        )

        try:
            entries = []

            for entry in os.scandir(
                pending_folder
            ):
                try:
                    if not entry.is_file():
                        continue

                    extension = os.path.splitext(
                        entry.name
                    )[1].lower()

                    if extension not in allowed_extensions:
                        continue

                    entries.append(entry)

                except OSError:
                    continue

            if not entries:
                print(
                    "No ASN files found in Pending:",
                    pending_folder,
                )
                return []

            csv_files = [
                entry
                for entry in entries
                if os.path.splitext(
                    entry.name
                )[1].lower() == ".csv"
            ]

            candidates = (
                csv_files
                if csv_files
                else entries
            )

            # OLDEST FIRST.
            candidates.sort(
                key=lambda entry: (
                    entry.stat().st_mtime,
                    entry.name.lower(),
                )
            )

            files = [
                os.path.abspath(
                    entry.path
                )
                for entry in candidates
            ]

            print()
            print("Pending ASN queue:")
            for index, file_path in enumerate(
                files,
                start=1,
            ):
                print(
                    f"  {index:02d}. "
                    f"{os.path.basename(file_path)}"
                )

            return files

        except Exception as error:
            print(
                "Could not read ASN Pending folder:",
                repr(error),
            )
            return []


    def _get_next_pending_asn_file(self, folder_path):
        """
        Return the oldest Pending ASN file.
        """

        files = self._get_pending_asn_files(
            folder_path
        )

        if not files:
            return None

        return files[0]


    def _move_completed_asn_file(
        self,
        file_path,
        f_path,
    ):
        """
        Move a successfully processed ASN file:

            F_PATH/Pending/file.csv
                ->
            F_PATH/Completed/file.csv

        The file is moved ONLY after AUTO_STATUS has been updated.
        """

        if not file_path:
            return False

        if not f_path:
            return False

        source = Path(
            file_path
        )

        completed_folder = (
            Path(f_path) / "Completed"
        )

        try:
            completed_folder.mkdir(
                parents=True,
                exist_ok=True,
            )

            if not source.is_file():
                print(
                    "Completed ASN source file does not exist:",
                    source,
                )
                return False

            destination = (
                completed_folder /
                source.name
            )

            # Do not overwrite an existing completed file.
            # A timestamped filename should normally make this impossible.
            if destination.exists():
                timestamp = datetime.now().strftime(
                    "%Y%m%d_%H%M%S_%f"
                )[:-3]

                destination = (
                    completed_folder /
                    f"{source.stem}_{timestamp}{source.suffix}"
                )

            shutil.move(
                str(source),
                str(destination),
            )

            print("=" * 70)
            print("ASN FILE MOVED TO COMPLETED")
            print("=" * 70)
            print("FROM:", source)
            print("TO  :", destination)
            print("=" * 70)

            return True

        except Exception as error:
            print(
                "Could not move completed ASN file:",
                repr(error),
            )
            return False


    # ------------------------------------------------------------------------
    # ASN QUEUE - PROCESS ONE UPLOAD ASN PAGE
    # ------------------------------------------------------------------------

    def _process_current_asn_upload_page(
        self,
        timeout=60,
    ):
        """
        Process exactly ONE file from F_PATH/Pending.

        Flow:
            Pending oldest file
                -> Upload ASN
                -> ASN creation / already-created confirmation
                -> capture invoice numbers
                -> AUTO_STATUS = 1
                -> Doc Upload search
                -> move CSV to Completed

        If any required step fails, the file remains in Pending.
        """

        if self.driver is None:
            print(
                "ASN queue: Edge driver is unavailable."
            )
            return False

        # -------------------------------------------------------------
        # VERIFY CURRENT UPLOAD ASN PAGE
        # -------------------------------------------------------------

        print("Verifying Upload ASN page...")

        verification_end = (
            time.time() + 20
        )

        verified = False

        while time.time() < verification_end:

            try:
                current_url = (
                    self.driver.current_url
                    or ""
                )

                title = (
                    self.driver.title
                    or ""
                )

                body_text = ""

                try:
                    body_text = (
                        self.driver.find_element(
                            By.TAG_NAME,
                            "body",
                        ).text
                        or ""
                    ).lower()

                except Exception:
                    pass

                print(
                    "Upload ASN verification:",
                    current_url,
                    "| title:",
                    title,
                )

                if (
                    "zasnupload" in current_url.lower()
                    or "upload.htm" in current_url.lower()
                    or "upload asn" in body_text
                    or "uploadasn" in current_url.lower()
                ):
                    verified = True
                    break

            except Exception as error:
                print(
                    "Upload ASN verification warning:",
                    repr(error),
                )

            time.sleep(0.5)

        if not verified:
            print(
                "Upload ASN page could not be verified."
            )
            return False

        print("=" * 70)
        print("UPLOAD ASN PAGE VERIFIED")
        print("Current URL:", self.driver.current_url)
        print("Current title:", self.driver.title)
        print("=" * 70)

        # -------------------------------------------------------------
        # SELECT OLDEST PENDING FILE
        # -------------------------------------------------------------

        if not self._select_asn_file_from_db(
            timeout=30
        ):
            print("=" * 70)
            print("ASN FILE SELECTION FAILED")
            print("No Pending ASN file was selected.")
            print("=" * 70)
            return False

        # -------------------------------------------------------------
        # CLICK UPLOAD
        # -------------------------------------------------------------

        if not self._click_asn_upload_button(
            timeout=30
        ):
            print("=" * 70)
            print("ASN UPLOAD BUTTON CLICK FAILED")
            print("The selected file remains in Pending.")
            print("=" * 70)
            return False

        print("=" * 70)
        print("ASN FILE SELECTED AND UPLOAD BUTTON CLICKED")
        print(
            "FILE:",
            self.current_asn_file_path,
        )
        print("=" * 70)

        # -------------------------------------------------------------
        # WAIT FOR ASN CREATION
        # -------------------------------------------------------------

        if not self._wait_for_asn_creation(
            timeout=timeout
        ):
            print(
                "ASN creation could not be confirmed."
            )
            print(
                "Pending file will NOT be moved."
            )
            return False

        # -------------------------------------------------------------
        # GET INVOICE NUMBERS
        # -------------------------------------------------------------

        invoice_numbers = list(
            dict.fromkeys(
                self.created_asn_invoice_numbers
                or []
            )
        )

        if not invoice_numbers:

            try:
                body_text = (
                    self.driver.find_element(
                        By.TAG_NAME,
                        "body",
                    ).text
                    or ""
                )

                invoice_numbers = list(
                    dict.fromkeys(
                        re.findall(
                            r"\bP\d{6,20}\b",
                            body_text,
                            flags=re.IGNORECASE,
                        )
                    )
                )

            except Exception as error:
                print(
                    "Invoice body-text fallback warning:",
                    repr(error),
                )

        if not invoice_numbers:
            print("=" * 70)
            print(
                "ASN WAS CONFIRMED BUT NO INVOICE NUMBER "
                "COULD BE IDENTIFIED."
            )
            print(
                "AUTO_STATUS cannot be safely updated."
            )
            print(
                "Pending file will remain in Pending."
            )
            print("=" * 70)
            return False

        self.created_asn_invoice_numbers = list(
            dict.fromkeys(
                invoice_numbers
            )
        )

        print(
            "Created ASN invoice numbers:",
            self.created_asn_invoice_numbers,
        )

        # -------------------------------------------------------------
        # UPDATE AUTO_STATUS
        # -------------------------------------------------------------

        status_updated = (
            self._update_invoice_auto_status(
                self.created_asn_invoice_numbers,
                auto_status=1,
            )
        )

        if not status_updated:
            print("=" * 70)
            print(
                "AUTO_STATUS UPDATE FAILED"
            )
            print(
                "Pending file will remain in Pending."
            )
            print("=" * 70)
            return False

        # -------------------------------------------------------------
        # DOC UPLOAD
        # -------------------------------------------------------------

        print("=" * 70)
        print("ASN CREATED + AUTO_STATUS UPDATED")
        print("Continuing to DOC UPLOAD...")
        print("=" * 70)

        if not self._open_doc_upload_and_search(
            timeout=40
        ):
            print("=" * 70)
            print("DOC UPLOAD SEARCH FLOW FAILED")
            print(
                "AUTO_STATUS is already 1."
            )
            print(
                "Pending file is NOT moved because the complete "
                "workflow did not finish."
            )
            print("=" * 70)
            return False

        # -------------------------------------------------------------
        # MOVE FILE ONLY AFTER COMPLETE SUCCESS
        # -------------------------------------------------------------

        f_path = self._get_asn_file_path_from_db()

        if not f_path:
            print(
                "F_PATH could not be loaded after ASN completion."
            )
            return False

        if not self._move_completed_asn_file(
            self.current_asn_file_path,
            f_path,
        ):
            print(
                "WARNING: ASN workflow completed, but the CSV "
                "could not be moved to Completed."
            )
            return False

        # Reset current file after it has been moved.
        self.current_asn_file_path = None

        print("=" * 70)
        print("ONE ASN QUEUE ITEM COMPLETED")
        print("=" * 70)

        return True


    # ------------------------------------------------------------------------
    # ASN CREATION - WAIT FOR SUCCESS
    # ------------------------------------------------------------------------

    def _wait_for_asn_creation(self, timeout=60):
        """
        Wait for the ASN upload page to reach a terminal state.

        IMPORTANT:
        Mahindra can return:
            "Data Uploaded..."
        for a successful upload, OR
            "ASN <number> is already created for the entered combination..."
        when the ASN already exists.

        The second case is NOT a reason to keep waiting forever.  It is a
        terminal state and the workflow can continue to the barcode/doc-upload
        steps.
        """
        if self.driver is None:
            return False

        print("STEP 9: Waiting for ASN creation / existing-ASN confirmation...")

        end_time = time.time() + timeout

        while time.time() < end_time:
            if self._stop_event.is_set():
                return False

            try:
                self.driver.switch_to.default_content()

                body_text = (
                    self.driver.find_element(
                        By.TAG_NAME,
                        "body",
                    ).text or ""
                )

                body_lower = body_text.lower()

                # ---------------------------------------------------------
                # Read invoice numbers directly from the complete page text.
                # This is deliberately independent of table structure.
                # Example:
                #     Invoice No
                #     P26101416
                # ---------------------------------------------------------
                invoice_numbers = list(
                    dict.fromkeys(
                        re.findall(
                            r"\bP\d{6,20}\b",
                            body_text,
                            flags=re.IGNORECASE,
                        )
                    )
                )

                # Also try the existing DOM/table extractor.
                try:
                    extracted = self._get_created_asn_invoice_numbers(
                        quiet=True
                    )
                    for value in extracted:
                        value = str(value or "").strip()
                        if (
                            value
                            and re.fullmatch(
                                r"[A-Za-z0-9/_-]{3,50}",
                                value,
                            )
                            and value not in invoice_numbers
                        ):
                            invoice_numbers.append(value)
                except Exception as error:
                    print(
                        "Invoice extractor fallback warning:",
                        repr(error),
                    )

                # ---------------------------------------------------------
                # SUCCESS CASE
                # ---------------------------------------------------------
                success_markers = (
                    "data uploaded",
                    "upload successful",
                    "uploaded successfully",
                    "asn created",
                    "asn generated",
                )

                success_text_found = any(
                    marker in body_lower
                    for marker in success_markers
                )

                if success_text_found and invoice_numbers:
                    self.created_asn_invoice_numbers = list(
                        dict.fromkeys(invoice_numbers)
                    )

                    print(
                        "ASN creation confirmed.",
                        "Invoices:",
                        self.created_asn_invoice_numbers,
                    )
                    return True

                # ---------------------------------------------------------
                # ALREADY-CREATED CASE
                # ---------------------------------------------------------
                already_created = (
                    "already created" in body_lower
                    or "asn is already created" in body_lower
                    or "asn " in body_lower
                    and "is already created for the entered combination" in body_lower
                )

                if already_created:
                    print(
                        "Mahindra reports ASN is already created.",
                        "This is a terminal state; continuing workflow.",
                        "Invoices:",
                        invoice_numbers,
                    )

                    # If the invoice number is visible, continue immediately.
                    self.created_asn_invoice_numbers = list(
                        dict.fromkeys(invoice_numbers)
                    )

                    # Even if the invoice text is temporarily not rendered,
                    # the page itself has reached a terminal state. Continue
                    # so the barcode/doc-upload flow is not blocked forever.
                    return True

                print(
                    "Waiting for ASN creation...",
                    f"success_text={success_text_found}",
                    f"already_created={already_created}",
                    f"invoices={invoice_numbers}",
                )

            except Exception as error:
                print(
                    "ASN creation confirmation check warning:",
                    repr(error),
                )

            time.sleep(0.7)

        print(
            "ASN creation confirmation timed out after",
            timeout,
            "seconds.",
        )
        return False


    # ------------------------------------------------------------------------
    # ASN PAGE - READ CREATED INVOICE NUMBERS
    # ------------------------------------------------------------------------

    def _get_created_asn_invoice_numbers(self, quiet=False):
        """
        Read Invoice No values from the created ASN grid.

        The screenshot shows a table with the column:
            Invoice No

        This method finds the column by its header text instead of relying on
        a fragile row/cell XPath. It returns unique invoice numbers such as:
            P26101166
            P26101167
        """
        if self.driver is None:
            return []

        try:
            self.driver.switch_to.default_content()

            script = r"""
            (() => {
                const normalize = value =>
                    (value || '')
                        .replace(/\s+/g, ' ')
                        .trim();

                const tables = Array.from(
                    document.querySelectorAll('table')
                );

                const invoiceValues = [];

                for (const table of tables) {
                    const rows = Array.from(
                        table.querySelectorAll('tr')
                    );

                    if (!rows.length) {
                        continue;
                    }

                    let headerRow = null;
                    let headerCells = [];
                    let invoiceIndex = -1;

                    for (const row of rows) {
                        const cells = Array.from(
                            row.querySelectorAll('th, td')
                        );

                        if (!cells.length) {
                            continue;
                        }

                        const values = cells.map(cell =>
                            normalize(
                                cell.innerText ||
                                cell.textContent ||
                                cell.value || ''
                            )
                        );

                        const index = values.findIndex(value =>
                            value.toLowerCase() === 'invoice no' ||
                            value.toLowerCase() === 'invoice number' ||
                            value.toLowerCase() === 'invoice'
                        );

                        if (index >= 0) {
                            headerRow = row;
                            headerCells = cells;
                            invoiceIndex = index;
                            break;
                        }
                    }

                    if (!headerRow || invoiceIndex < 0) {
                        continue;
                    }

                    const headerRowIndex = rows.indexOf(headerRow);

                    for (let i = headerRowIndex + 1; i < rows.length; i++) {
                        const cells = Array.from(
                            rows[i].querySelectorAll('td, th')
                        );

                        if (cells.length <= invoiceIndex) {
                            continue;
                        }

                        const value = normalize(
                            cells[invoiceIndex].innerText ||
                            cells[invoiceIndex].textContent ||
                            cells[invoiceIndex].value || ''
                        );

                        if (value) {
                            invoiceValues.push(value);
                        }
                    }
                }

                // Fallback for pages that render the grid using divs instead
                // of a native table.
                if (!invoiceValues.length) {
                    const allText = normalize(
                        document.body?.innerText || ''
                    );

                    const matches = allText.match(/\bP\d{6,20}\b/g) || [];

                    invoiceValues.push(...matches);
                }

                return Array.from(
                    new Set(invoiceValues)
                );
            })();
            """

            result = self.driver.execute_script(script)

            values = []

            if isinstance(result, list):
                for value in result:
                    value = str(value or '').strip()

                    # Mahindra invoice numbers in the current page are like
                    # P26101166. Keep the filter broad enough for future data.
                    if re.fullmatch(r'[A-Za-z0-9/_-]{3,50}', value):
                        values.append(value)

            # Remove duplicates while preserving page order.
            unique_values = list(dict.fromkeys(values))

            # Final fallback for SAP/BSP pages where the invoice grid is
            # rendered through non-table elements or an unusual DOM layer.
            if not unique_values:
                try:
                    body_text = (
                        self.driver.find_element(
                            By.TAG_NAME,
                            "body",
                        ).text or ""
                    )

                    regex_values = re.findall(
                        r"\bP\d{6,20}\b",
                        body_text,
                        flags=re.IGNORECASE,
                    )

                    unique_values = list(
                        dict.fromkeys(
                            str(value).strip()
                            for value in regex_values
                            if value
                        )
                    )
                except Exception:
                    pass

            if not quiet:
                print(
                    "Invoice No values read from created ASN page:",
                    unique_values,
                )

            return unique_values

        except Exception as error:
            if not quiet:
                print(
                    "Could not read Invoice No from ASN page:",
                    repr(error),
                )
            return []

    # ------------------------------------------------------------------------
    # DATABASE - UPDATE Auto_Status FOR CREATED ASN INVOICES
    # ------------------------------------------------------------------------

    def _get_source_db_connection(self):
        """
        Open the SOURCE database connection.

        IMPORTANT:
        - dbo.SETTINGS / dbo.MailSettings are in the Settings database and
          continue to use database.get_connection().
        - dbo.IRPEWBInvoice is in SOURCE_DB_DATABASE and MUST use this
          connection.
        """
        database_name = str(SOURCE_DB_DATABASE or "").strip()

        if not database_name:
            raise RuntimeError(
                "SOURCE_DB_DATABASE is empty. Expected HSI(P)_BKP_29082026."
            )

        if not DB_SERVER or not DB_USERNAME or not DB_DRIVER:
            raise RuntimeError(
                "SQL Server configuration is incomplete. Check DB_SERVER, "
                "DB_USERNAME and DB_DRIVER in config.py."
            )

        connection_string = (
            f"DRIVER={{{DB_DRIVER}}};"
            f"SERVER={DB_SERVER};"
            f"DATABASE={database_name};"
            f"UID={DB_USERNAME};"
            f"PWD={DB_PASSWORD};"
            "TrustServerCertificate=yes;"
        )

        return pyodbc.connect(connection_string)

    def _update_invoice_auto_status(self, invoice_numbers, auto_status=1):
        """
        Update dbo.IRPEWBInvoice.Auto_Status using Invoice No only.

        Mahindra ASN No is intentionally NOT used.

        Mapping:
            Mahindra Invoice No -> SOURCE DB dbo.IRPEWBInvoice.DocNo

        SOURCE DATABASE:
            SOURCE_DB_DATABASE (for example HSI(P)_BKP_29082026)

        SETTINGS DATABASE:
            database.get_connection() remains used by the rest of this file
            for dbo.SETTINGS and dbo.MailSettings.
        """
        if not invoice_numbers:
            print("Auto_Status update skipped: no invoice numbers.")
            return False

        connection = None
        cursor = None

        try:
            cleaned_numbers = []

            for value in invoice_numbers:
                value = str(value or "").strip()
                if value and value not in cleaned_numbers:
                    cleaned_numbers.append(value)

            if not cleaned_numbers:
                print("Auto_Status update skipped: invoice list is empty.")
                return False

            print("STEP 10: UPDATING IRPEWBInvoice.Auto_Status")
            print("IMPORTANT: ASN No is NOT used for this update.")
            print("Invoice Nos:", cleaned_numbers)
            print("Target Auto_Status:", auto_status)
            print("Source database:", SOURCE_DB_DATABASE)

            # CRITICAL FIX: do NOT call get_connection() here. That connection
            # points to the Settings database (HSI_Automation).
            connection = self._get_source_db_connection()
            cursor = connection.cursor()

            # Show the actual database used by this SQL connection.
            cursor.execute("SELECT DB_NAME()")
            actual_database = cursor.fetchone()[0]
            print("Python SQL source database:", actual_database)

            # Verify that the expected table exists in the SOURCE database.
            cursor.execute("""
                SELECT COUNT(*)
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = 'dbo'
                  AND TABLE_NAME = 'IRPEWBInvoice'
            """)

            table_exists = int(cursor.fetchone()[0] or 0) > 0

            if not table_exists:
                raise RuntimeError(
                    f"dbo.IRPEWBInvoice does not exist in source database "
                    f"'{actual_database}'."
                )

            placeholders = ",".join("?" for _ in cleaned_numbers)

            # First verify how many invoice rows exist. This prevents the
            # automation from claiming success when DocNo does not match.
            select_sql = f"""
                SELECT DocNo, Auto_Status
                FROM dbo.IRPEWBInvoice
                WHERE DocNo IN ({placeholders})
            """

            cursor.execute(select_sql, cleaned_numbers)
            existing_rows = cursor.fetchall()

            print("Matching IRPEWBInvoice rows found:", len(existing_rows))

            if not existing_rows:
                connection.rollback()
                print("ERROR: None of the Invoice Nos matched dbo.IRPEWBInvoice.DocNo.")
                print("Invoice Nos checked:", cleaned_numbers)
                return False

            found_doc_nos = []
            for row in existing_rows:
                doc_no = str(row[0] or "").strip()
                current_status = row[1]
                found_doc_nos.append(doc_no)
                print(
                    f"DocNo={doc_no} | Current Auto_Status={current_status} "
                    f"| Target={auto_status}"
                )

            # Update ONLY DocNo. ASN number is never referenced.
            update_sql = f"""
                UPDATE dbo.IRPEWBInvoice
                SET Auto_Status = ?
                WHERE DocNo IN ({placeholders})
            """

            cursor.execute(
                update_sql,
                [auto_status] + cleaned_numbers,
            )

            affected_rows = cursor.rowcount

            connection.commit()

            print("IRPEWBInvoice Auto_Status UPDATE SUCCESS")
            print("Rows affected:", affected_rows)

            # Verify after COMMIT.
            verify_sql = f"""
                SELECT DocNo, Auto_Status
                FROM dbo.IRPEWBInvoice
                WHERE DocNo IN ({placeholders})
            """

            cursor.execute(verify_sql, cleaned_numbers)
            verify_rows = cursor.fetchall()

            verified_count = 0

            for row in verify_rows:
                doc_no = str(row[0] or "").strip()
                status = row[1]
                print(
                    f"VERIFY: DocNo={doc_no} | Auto_Status={status}"
                )

                try:
                    if int(status) == int(auto_status):
                        verified_count += 1
                except (TypeError, ValueError):
                    pass

            if verified_count != len(found_doc_nos):
                print(
                    "ERROR: Auto_Status verification did not match all "
                    "existing invoice rows."
                )
                return False

            print(
                f"Auto_Status=1 verified for {verified_count} invoice(s)."
            )

            return True

        except Exception as error:
            print("IRPEWBInvoice Auto_Status UPDATE FAILED")
            print("Error:", repr(error))

            if connection is not None:
                try:
                    connection.rollback()
                except Exception:
                    pass

            return False

        finally:
            try:
                if cursor is not None:
                    cursor.close()
            except Exception:
                pass

            try:
                if connection is not None:
                    connection.close()
            except Exception:
                pass

    # ------------------------------------------------------------------------
    # ASN BARCODE - DOWNLOAD PDF
    # ------------------------------------------------------------------------

    def _download_asn_barcode(self, timeout=60):
        """
        Click Mahindra's Download ASN Barcode button and wait for the PDF.

        Exact XPath supplied by the user:
            //*[@id="DownloadBarCode"]

        Edge's download directory is configured from:
            dbo.SETTINGS.ASN_BARCODE_PATH
        """
        if self.driver is None:
            print("ASN Barcode download: Edge driver is unavailable.")
            return False

        download_xpath = '//*[@id="DownloadBarCode"]'

        # Reload the configured directory in case Settings changed while the
        # browser was already open.
        download_dir = self._get_asn_barcode_path_from_db()

        if not download_dir:
            print("ASN Barcode download path is missing.")
            return False

        download_dir = os.path.abspath(
            os.path.expandvars(
                download_dir.strip('"').strip("'").strip()
            )
        )

        try:
            os.makedirs(download_dir, exist_ok=True)
        except Exception as error:
            print(
                "ASN Barcode download folder is unavailable:",
                repr(error),
            )
            return False

        self.asn_barcode_download_dir = download_dir

        # -------------------------------------------------------------
        # Snapshot existing PDFs so an older file is not mistaken for the
        # newly generated ASN Barcode PDF.
        # -------------------------------------------------------------
        before_files = {}

        try:
            for entry in os.scandir(download_dir):
                if not entry.is_file():
                    continue

                if os.path.splitext(entry.name)[1].lower() != '.pdf':
                    continue

                try:
                    before_files[entry.path] = entry.stat().st_mtime_ns
                except OSError:
                    pass
        except Exception as error:
            print(
                "Could not snapshot ASN Barcode folder:",
                repr(error),
            )

        print("STEP 11: Clicking Download ASN Barcode...")
        print("Download ASN Barcode XPath:", download_xpath)
        print("ASN Barcode PDF folder:", download_dir)

        try:
            self.driver.switch_to.default_content()

            wait = WebDriverWait(
                self.driver,
                timeout,
            )

            download_button = wait.until(
                EC.visibility_of_element_located(
                    (By.XPATH, download_xpath)
                )
            )

            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});",
                    download_button,
                )
            except Exception:
                pass

            try:
                wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH, download_xpath)
                    )
                )
            except Exception:
                pass

            try:
                download_button.click()
            except Exception as click_error:
                print(
                    "Normal Download ASN Barcode click failed. "
                    "Using JavaScript click:",
                    repr(click_error),
                )

                self.driver.execute_script(
                    "arguments[0].click();",
                    download_button,
                )

            print("Download ASN Barcode button clicked.")

        except TimeoutException:
            print(
                "Download ASN Barcode button was not found. XPath:",
                download_xpath,
            )
            return False

        except Exception as error:
            print(
                "Download ASN Barcode click failed:",
                repr(error),
            )
            return False

        # -------------------------------------------------------------
        # WAIT FOR PDF
        # -------------------------------------------------------------
        end_time = time.time() + timeout

        while time.time() < end_time:
            if self._stop_event.is_set():
                return False

            try:
                # Ignore temporary Chromium/Edge download files.
                current_pdfs = []

                for entry in os.scandir(download_dir):
                    try:
                        if not entry.is_file():
                            continue

                        if os.path.splitext(entry.name)[1].lower() != '.pdf':
                            continue

                        stat = entry.stat()
                        old_mtime = before_files.get(entry.path)

                        # New file or overwritten/updated existing file.
                        if (
                            old_mtime is None
                            or stat.st_mtime_ns > old_mtime
                        ):
                            current_pdfs.append(entry.path)

                    except OSError:
                        continue

                # Do not finish while Edge is still downloading a temporary
                # .crdownload file.
                downloading = False

                try:
                    downloading = any(
                        entry.is_file()
                        and entry.name.lower().endswith('.crdownload')
                        for entry in os.scandir(download_dir)
                    )
                except Exception:
                    pass

                if current_pdfs and not downloading:
                    # The newest changed PDF is the file generated by this
                    # Download ASN Barcode action.
                    downloaded_pdf = max(
                        current_pdfs,
                        key=lambda path: os.path.getmtime(path),
                    )

                    # Make sure the file has a non-zero size and is readable.
                    try:
                        file_size = os.path.getsize(downloaded_pdf)
                    except OSError:
                        file_size = 0

                    if file_size > 0:
                        print("ASN Barcode PDF downloaded successfully:")
                        print("PDF:", downloaded_pdf)
                        print("Size:", file_size, "bytes")
                        print("Folder:", download_dir)
                        return True

            except Exception as error:
                print(
                    "Waiting for ASN Barcode PDF warning:",
                    repr(error),
                )

            time.sleep(0.5)

        print(
            "ASN Barcode PDF download timed out after",
            timeout,
            "seconds.",
        )
        print(
            "Expected download folder:",
            download_dir,
        )
        return False

    # ------------------------------------------------------------------------
    # ASN FILE - LOAD F_PATH FROM DATABASE
    # ------------------------------------------------------------------------

    def _get_asn_file_path_from_db(self):
        """
        Read F_PATH dynamically from dbo.SETTINGS.

        SYSTEM_NAME is intentionally NOT checked.
        The latest settings row is used.
        """
        connection = None
        cursor = None

        try:
            print("=" * 70)
            print("LOADING ASN F_PATH FROM dbo.SETTINGS")
            print("SYSTEM_NAME CHECK: DISABLED")

            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT TOP 1 F_PATH
                FROM dbo.SETTINGS
                ORDER BY ID DESC
                """
            )

            row = cursor.fetchone()
            if not row:
                print("No configuration found in dbo.SETTINGS.")
                return None

            f_path = str(row[0] or "").strip()
            if not f_path:
                print("F_PATH is empty in dbo.SETTINGS.")
                return None

            f_path = f_path.strip('"').strip("'").strip()
            f_path = os.path.expandvars(f_path)

            print("ASN F_PATH loaded from database:", f_path)
            return f_path

        except Exception as error:
            print("Could not load ASN F_PATH from dbo.SETTINGS:", repr(error))
            return None

        finally:
            try:
                if cursor is not None:
                    cursor.close()
            except Exception:
                pass

            try:
                if connection is not None:
                    connection.close()
            except Exception:
                pass

    def _get_asn_barcode_path_from_db(self):
        """
        Read ASN_BARCODE_PATH from dbo.SETTINGS.

        The current workflow skips ASN Barcode PDF download. This method is
        retained for compatibility with the existing barcode-download method.
        """
        connection = None
        cursor = None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT TOP 1 ASN_BARCODE_PATH
                FROM dbo.SETTINGS
                ORDER BY ID DESC
                """
            )

            row = cursor.fetchone()

            if not row:
                print("ASN_BARCODE_PATH: no settings row found.")
                return None

            value = str(row[0] or "").strip()

            if not value:
                print("ASN_BARCODE_PATH is empty in dbo.SETTINGS.")
                return None

            value = value.strip('"').strip("'").strip()
            value = os.path.expandvars(value)

            print("ASN Barcode path loaded from database:", value)
            return value

        except Exception as error:
            print(
                "Could not load ASN_BARCODE_PATH from dbo.SETTINGS:",
                repr(error),
            )
            return None

        finally:
            try:
                if cursor is not None:
                    cursor.close()
            except Exception:
                pass

            try:
                if connection is not None:
                    connection.close()
            except Exception:
                pass


    def _select_asn_file_from_db(self, timeout=30):
        """
        Get F_PATH from dbo.SETTINGS, find the latest ASN file, and pass
        the full path directly to the HTML <input type="file"> element.

        Exact file input XPath from the Mahindra Upload ASN page:
            //*[@id="myUpload"]
        """
        if self.driver is None:
            print("ASN file selection: Edge driver is unavailable.")
            return False

        f_path = self._get_asn_file_path_from_db()

        if not f_path:
            return False

        print("Resolved ASN F_PATH:", f_path)

        file_path = self._get_next_pending_asn_file(
            f_path
        )

        if not file_path:
            print(
                "No Pending ASN file is available."
            )
            return False

        if not os.path.isfile(file_path):
            print("ASN file does not exist:", file_path)
            return False

        self.current_asn_file_path = file_path

        file_input_xpath = '//*[@id="myUpload"]'

        print("STEP 7: Selecting ASN file...")
        print("File input XPath:", file_input_xpath)
        print("File to select:", file_path)

        try:
            wait = WebDriverWait(self.driver, timeout)

            self.driver.switch_to.default_content()

            file_input = wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, file_input_xpath)
                )
            )

            # <input type="file"> accepts the local absolute path through
            # Selenium. This avoids opening the Windows File Explorer dialog.
            file_input.send_keys(file_path)

            # Verify the browser accepted the file.
            try:
                selected_value = file_input.get_attribute("value") or ""
                print("File input value after selection:", selected_value)
            except Exception:
                selected_value = ""

            print("ASN file path passed successfully.")
            print("Selected ASN file:", file_path)

            return True

        except TimeoutException:
            print(
                "ASN file input was not found. XPath:",
                file_input_xpath,
            )
            self.current_asn_file_path = None
            return False

        except Exception as error:
            print(
                "Could not pass ASN file path to myUpload:",
                repr(error),
            )
            self.current_asn_file_path = None
            return False

    def _click_asn_upload_button(self, timeout=30):
        """
        Click the Mahindra "Click to Upload File" control.

        Exact XPath supplied from the current Mahindra DOM:
            //*[@id="submitButton"]/span

        The span is clicked first. If that is not clickable, the parent
        #submitButton element is used as a fallback.
        """
        if self.driver is None:
            print("ASN upload button: Edge driver is unavailable.")
            return False

        span_xpath = '//*[@id="submitButton"]/span'
        button_xpath = '//*[@id="submitButton"]'

        print("STEP 8: Clicking 'Click to Upload File'...")
        print("Upload button span XPath:", span_xpath)

        try:
            self.driver.switch_to.default_content()

            wait = WebDriverWait(self.driver, timeout)

            # Wait for the exact span supplied by the user.
            upload_span = wait.until(
                EC.visibility_of_element_located(
                    (By.XPATH, span_xpath)
                )
            )

            try:
                self.driver.execute_script(
                    """
                    arguments[0].scrollIntoView({
                        behavior: 'instant',
                        block: 'center',
                        inline: 'center'
                    });
                    """,
                    upload_span,
                )
            except Exception:
                pass

            try:
                wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH, span_xpath)
                    )
                )
                upload_span.click()
                print(
                    "Click to Upload File clicked using:",
                    span_xpath,
                )
            except Exception as span_error:
                print(
                    "Span click failed. Trying parent #submitButton:",
                    repr(span_error),
                )

                upload_button = wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH, button_xpath)
                    )
                )

                try:
                    upload_button.click()
                except Exception:
                    self.driver.execute_script(
                        "arguments[0].click();",
                        upload_button,
                    )

                print(
                    "Click to Upload File clicked using:",
                    button_xpath,
                )

            time.sleep(2)

            return True

        except TimeoutException:
            print(
                "Click to Upload File control was not found.",
                "Span XPath:",
                span_xpath,
            )
            return False

        except Exception as error:
            print(
                "ASN upload button click failed:",
                repr(error),
            )
            return False

    # ------------------------------------------------------------------------
    # DOC UPLOAD -> SEARCH CRITERIA -> DATE RANGE -> MATERIAL -> SUBMIT
    # ------------------------------------------------------------------------

    DOC_UPLOAD_URL = (
        "https://srmapps.mahindra.com/sap/bc/ui5_ui5/ui2/ushell/"
        "shells/abap/fiorilaunchpad.html?"
        "sap-ushell-config=headerless&sap-client=100&sap-language=EN&"
        "sap-sec_session_created=X#zmm_supplier-display"
    )

    def _switch_to_self_service_tab(self, timeout=20):
        """
        Find the Mahindra Self Service tab which contains Doc Upload.

        We do not assume a fixed window-handle order because the portal can
        open several SAP tabs during the workflow.
        """
        if self.driver is None:
            return False

        end_time = time.time() + timeout

        while time.time() < end_time:
            if self._stop_event.is_set():
                return False

            try:
                handles = list(self.driver.window_handles)
            except Exception:
                handles = []

            for handle in handles:
                try:
                    self.driver.switch_to.window(handle)
                    self.driver.switch_to.default_content()

                    current_url = (self.driver.current_url or "").lower()

                    # First use the exact Doc Upload element.
                    elements = self.driver.find_elements(
                        By.XPATH,
                        '//*[@id="start_InvUpl"]',
                    )

                    for element in elements:
                        try:
                            if element.is_displayed():
                                print("Self Service tab found using start_InvUpl.")
                                print("Self Service URL:", self.driver.current_url)
                                return True
                        except Exception:
                            continue

                    # URL fallback for the known Mahindra Self Service page.
                    if (
                        "srmsus/default.htm" in current_url
                        or "zmm_supplier-display" in current_url
                    ):
                        print("Self Service tab found by URL.")
                        print("Self Service URL:", self.driver.current_url)
                        return True

                except Exception:
                    continue

            time.sleep(0.5)

        print("Mahindra Self Service tab containing Doc Upload was not found.")
        return False

    def _open_doc_upload_and_search(self, timeout=40):
        """
        Complete the requested post-ASN flow:

            ASN Barcode skipped
                -> Self Service tab
                -> Doc Upload (start_InvUpl)
                -> NEW Edge tab
                -> Search (__xmlview0--serach1)
                -> Search Criteria
                -> From Date icon (fromdate-icon)
                -> select today - 2 days
                -> To Date icon (todate-icon)
                -> select today
                -> Material radio (//*[@id="RB1-12"]/div/svg)
                -> Submit (//*[@id="__button3-content"])
        """
        if self.driver is None:
            print("Doc Upload: Edge driver is unavailable.")
            return False

        print("=" * 70)
        print("STEP 12: OPENING DOC UPLOAD")
        print("=" * 70)

        if not self._switch_to_self_service_tab(timeout=20):
            return False

        self._bring_browser_to_front()

        doc_upload_xpath = '//*[@id="start_InvUpl"]'
        old_handles = set(self.driver.window_handles)

        # -------------------------------------------------------------
        # STEP 12A: CLICK DOC UPLOAD
        # -------------------------------------------------------------
        print("Doc Upload XPath:", doc_upload_xpath)

        clicked = False
        doc_href = ""

        try:
            element = WebDriverWait(self.driver, 15).until(
                EC.visibility_of_element_located(
                    (By.XPATH, doc_upload_xpath)
                )
            )

            try:
                doc_href = (
                    element.get_attribute("href")
                    or ""
                ).strip()
            except Exception:
                doc_href = ""

            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center', inline:'center'});",
                    element,
                )
            except Exception:
                pass

            try:
                element.click()
                clicked = True
                print("Doc Upload clicked using exact XPath.")
            except Exception as click_error:
                print(
                    "Normal Doc Upload click failed; trying JavaScript click:",
                    repr(click_error),
                )
                self.driver.execute_script(
                    "arguments[0].click();",
                    element,
                )
                clicked = True
                print("Doc Upload clicked using JavaScript.")

        except TimeoutException:
            print("Doc Upload element was not found:", doc_upload_xpath)

        # -------------------------------------------------------------
        # STEP 12B: GUARANTEE NEW TAB
        # -------------------------------------------------------------
        # The SAP launchpad link normally has target="_blank".
        # If the portal did not create a new tab, explicitly open the known
        # Doc Upload URL in a new tab.
        if clicked:
            end_time = time.time() + 15

            while time.time() < end_time:
                try:
                    current_handles = set(self.driver.window_handles)
                    new_handles = [
                        h for h in current_handles
                        if h not in old_handles
                    ]

                    if new_handles:
                        self.driver.switch_to.window(new_handles[-1])
                        print("Doc Upload NEW tab opened.")
                        break
                except Exception as error:
                    print("Waiting for Doc Upload new tab:", repr(error))

                time.sleep(0.4)
            else:
                # No new tab after the click. Use the href from the element,
                # or the exact URL supplied for this Mahindra page.
                try:
                    target_url = doc_href or self.DOC_UPLOAD_URL

                    print(
                        "Doc Upload did not open a new tab after click. "
                        "Opening the same page explicitly in a NEW tab."
                    )

                    self.driver.execute_script(
                        "window.open(arguments[0], '_blank');",
                        target_url,
                    )

                    end_time = time.time() + 15
                    while time.time() < end_time:
                        current_handles = set(self.driver.window_handles)
                        new_handles = [
                            h for h in current_handles
                            if h not in old_handles
                        ]

                        if new_handles:
                            self.driver.switch_to.window(new_handles[-1])
                            print("Doc Upload NEW tab opened by fallback.")
                            break

                        time.sleep(0.4)
                    else:
                        print("Doc Upload new tab could not be created.")
                        return False

                except Exception as error:
                    print("Doc Upload new-tab fallback failed:", repr(error))
                    return False
        else:
            # Exact element was not found. Use the exact URL supplied by the
            # user, but still open it in a NEW tab.
            try:
                print(
                    "Opening the supplied Doc Upload URL in a NEW tab:",
                    self.DOC_UPLOAD_URL,
                )

                self.driver.execute_script(
                    "window.open(arguments[0], '_blank');",
                    self.DOC_UPLOAD_URL,
                )

                end_time = time.time() + 15
                while time.time() < end_time:
                    current_handles = set(self.driver.window_handles)
                    new_handles = [
                        h for h in current_handles
                        if h not in old_handles
                    ]

                    if new_handles:
                        self.driver.switch_to.window(new_handles[-1])
                        print("Doc Upload NEW tab opened by URL fallback.")
                        break

                    time.sleep(0.4)
                else:
                    print("Doc Upload new tab could not be created.")
                    return False

            except Exception as error:
                print("Doc Upload URL fallback failed:", repr(error))
                return False

        # -------------------------------------------------------------
        # STEP 12C: VERIFY DOC UPLOAD PAGE
        # -------------------------------------------------------------
        print("Waiting for Doc Upload page...")

        page_ready = False
        end_time = time.time() + timeout

        while time.time() < end_time:
            try:
                self.driver.switch_to.default_content()

                current_url = (self.driver.current_url or "").lower()
                title = (self.driver.title or "").lower()

                body_text = ""
                try:
                    body_text = (
                        self.driver.find_element(
                            By.TAG_NAME,
                            "body",
                        ).text or ""
                    ).lower()
                except Exception:
                    pass

                if (
                    "__xmlview0--serach1" in body_text
                    or "purchase order list" in body_text
                    or "invoice/asn/po no" in body_text
                    or "doc upload" in title
                    or "zmm_supplier-display" in current_url
                ):
                    page_ready = True
                    print("Doc Upload page detected.")
                    print("Doc Upload URL:", self.driver.current_url)
                    break

            except Exception as error:
                print("Doc Upload page verification warning:", repr(error))

            time.sleep(0.5)

        if not page_ready:
            print("Doc Upload page was not detected.")
            print("Current URL:", self.driver.current_url)
            return False

        self._bring_browser_to_front()

        # -------------------------------------------------------------
        # STEP 12D: CLICK SEARCH
        # -------------------------------------------------------------
        search_xpath = '//*[@id="__xmlview0--serach1"]'

        print("STEP 13: Clicking Search...")
        print("Search XPath:", search_xpath)

        try:
            search_button = WebDriverWait(self.driver, 30).until(
                EC.visibility_of_element_located(
                    (By.XPATH, search_xpath)
                )
            )

            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center', inline:'center'});",
                    search_button,
                )
            except Exception:
                pass

            try:
                WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, search_xpath)
                    )
                )
            except Exception:
                pass

            try:
                search_button.click()
            except Exception as click_error:
                print(
                    "Search normal click failed; using JavaScript:",
                    repr(click_error),
                )
                self.driver.execute_script(
                    "arguments[0].click();",
                    search_button,
                )

            print("Search button clicked.")

        except TimeoutException:
            print("Search button not found:", search_xpath)
            return False
        except Exception as error:
            print("Search button click failed:", repr(error))
            return False

        # -------------------------------------------------------------
        # STEP 12E: WAIT FOR SEARCH CRITERIA
        # -------------------------------------------------------------
        from_icon_xpath = '//*[@id="fromdate-icon"]'
        to_icon_xpath = '//*[@id="todate-icon"]'
        material_xpath = '//*[@id="RB1-12-Button"]'
        submit_xpath = '//*[@id="__button3-content"]'

        try:
            WebDriverWait(self.driver, 20).until(
                EC.visibility_of_element_located(
                    (By.XPATH, from_icon_xpath)
                )
            )
            print("Search Criteria popup opened.")
        except TimeoutException:
            print("Search Criteria popup / From Date icon was not found.")
            return False

        # -------------------------------------------------------------
        # STEP 12F: FROM DATE = TODAY - 2 DAYS
        # -------------------------------------------------------------
        today = datetime.now().date()
        from_date = today - timedelta(days=2)

        print(
            "STEP 14: Selecting From Date:",
            from_date.strftime("%d-%m-%Y"),
        )

        if not self._select_doc_upload_date(
            icon_xpath=from_icon_xpath,
            target_date=from_date,
            label="From Date",
            timeout=20,
        ):
            return False

        # -------------------------------------------------------------
        # STEP 12G: TO DATE = TODAY
        # -------------------------------------------------------------
        print(
            "STEP 15: Selecting To Date:",
            today.strftime("%d-%m-%Y"),
        )

        if not self._select_doc_upload_date(
            icon_xpath=to_icon_xpath,
            target_date=today,
            label="To Date",
            timeout=20,
        ):
            return False

        # -------------------------------------------------------------
        # -------------------------------------------------------------
        # STEP 12H: SELECT MATERIAL
        # -------------------------------------------------------------
        # IMPORTANT:
        # The inspected SAP UI5 DOM shows:
        #
        #   <div id="RB1-12"
        #        role="radio"
        #        aria-checked="false"
        #        class="sapMRb sapMRbHasLabel">
        #
        #       <svg ...>
        #           <circle id="RB1-12-Button" ...></circle>
        #       </svg>
        #
        #       <input type="radio"
        #              id="RB1-12-RB"
        #              tabindex="-1">
        #
        #       <span id="RB1-12-label">Material</span>
        #   </div>
        #
        # RB1-12-Button is only the SVG circle/visual element.
        # Clicking that SVG circle does not reliably trigger the UI5
        # RadioButton change event.
        #
        # The correct click target is the UI5 radio container:
        #     //*[@id="RB1-12"]
        #
        # The label is also a valid fallback:
        #     //*[@id="RB1-12-label"]
        #
        # Native radio input fallback:
        #     //*[@id="RB1-12-RB"]

        self._close_doc_upload_date_picker("To Date")

        print("STEP 16: Selecting Material radio button...")

        material_container_xpath = '//*[@id="RB1-12"]'
        material_label_xpath = '//*[@id="RB1-12-label"]'
        material_input_xpath = '//*[@id="RB1-12-RB"]'

        try:
            # Re-find the UI5 radio container after the date picker closes.
            material_container = WebDriverWait(
                self.driver,
                20,
            ).until(
                EC.visibility_of_element_located(
                    (By.XPATH, material_container_xpath)
                )
            )

            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center', inline:'center'});",
                material_container,
            )
            time.sleep(0.3)

            # ---------------------------------------------------------
            # Check current state first.
            # ---------------------------------------------------------
            def material_is_selected(driver):
                try:
                    element = driver.find_element(
                        By.XPATH,
                        material_container_xpath,
                    )
                    return (
                        str(
                            element.get_attribute("aria-checked") or ""
                        ).lower()
                        == "true"
                    )
                except Exception:
                    return False

            if material_is_selected(self.driver):
                print("Material is already selected.")
            else:
                print(
                    "Material currently not selected. "
                    "Clicking UI5 radio container..."
                )

                # 1. Primary: click the complete UI5 RadioButton container.
                try:
                    material_container.click()
                    print("Material container clicked using Selenium.")
                except Exception as error:
                    print(
                        "Material container Selenium click failed:",
                        repr(error),
                    )

                    # 2. Fallback: click the Material label.
                    try:
                        material_label = WebDriverWait(
                            self.driver,
                            5,
                        ).until(
                            EC.element_to_be_clickable(
                                (By.XPATH, material_label_xpath)
                            )
                        )

                        material_label.click()
                        print("Material label clicked using Selenium.")
                    except Exception as label_error:
                        print(
                            "Material label click failed:",
                            repr(label_error),
                        )

                        # 3. Final fallback: trigger click on the UI5
                        #    container, NOT on the SVG circle.
                        material_container = self.driver.find_element(
                            By.XPATH,
                            material_container_xpath,
                        )

                        self.driver.execute_script(
                            """
                            const el = arguments[0];

                            el.scrollIntoView({
                                block: 'center',
                                inline: 'center'
                            });

                            el.dispatchEvent(
                                new MouseEvent('mousedown', {
                                    bubbles: true,
                                    cancelable: true,
                                    view: window
                                })
                            );

                            el.dispatchEvent(
                                new MouseEvent('mouseup', {
                                    bubbles: true,
                                    cancelable: true,
                                    view: window
                                })
                            );

                            el.click();
                            """,
                            material_container,
                        )

                        print(
                            "Material UI5 container clicked using JavaScript."
                        )

                time.sleep(0.7)

            # ---------------------------------------------------------
            # Verify UI5 state.
            # ---------------------------------------------------------
            material_selected = material_is_selected(self.driver)

            # Re-read the actual radio input as a second verification.
            try:
                material_input = self.driver.find_element(
                    By.XPATH,
                    material_input_xpath,
                )
                native_checked = bool(
                    self.driver.execute_script(
                        "return arguments[0].checked === true;",
                        material_input,
                    )
                )
            except Exception:
                native_checked = False

            print(
                "Material selection verification | "
                f"aria-checked={material_selected} | "
                f"native-checked={native_checked}"
            )

            if not (material_selected or native_checked):
                # One final attempt using the label.
                print(
                    "Material was not selected. "
                    "Performing final label JavaScript click..."
                )

                material_label = WebDriverWait(
                    self.driver,
                    5,
                ).until(
                    EC.presence_of_element_located(
                        (By.XPATH, material_label_xpath)
                    )
                )

                self.driver.execute_script(
                    "arguments[0].click();",
                    material_label,
                )

                time.sleep(0.7)

                material_selected = material_is_selected(self.driver)

                try:
                    material_input = self.driver.find_element(
                        By.XPATH,
                        material_input_xpath,
                    )
                    native_checked = bool(
                        self.driver.execute_script(
                            "return arguments[0].checked === true;",
                            material_input,
                        )
                    )
                except Exception:
                    native_checked = False

                print(
                    "Final Material verification | "
                    f"aria-checked={material_selected} | "
                    f"native-checked={native_checked}"
                )

            if not (material_selected or native_checked):
                raise RuntimeError(
                    "Material radio button could not be selected. "
                    "UI5 aria-checked is still false."
                )

            print("Material radio button selected successfully.")

        except TimeoutException:
            print(
                "Material radio container was not found:",
                material_container_xpath,
            )
            return False

        except Exception as error:
            print(
                "Material radio button selection failed:",
                repr(error),
            )
            return False

        # -------------------------------------------------------------
        # STEP 12I: SUBMIT
        # -------------------------------------------------------------
        print("STEP 17: Clicking Submit...")
        print("Submit XPath:", submit_xpath)

        try:
            # Re-find Submit after Material selection because Angular/UI5
            # can re-render the dialog controls.
            submit_content = WebDriverWait(
                self.driver,
                20,
            ).until(
                EC.visibility_of_element_located(
                    (By.XPATH, submit_xpath)
                )
            )

            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center', inline:'center'});",
                submit_content,
            )
            time.sleep(0.3)

            # Wait for the actual Submit element to be enabled.
            WebDriverWait(
                self.driver,
                10,
            ).until(
                lambda d: (
                    submit_content.is_displayed()
                    and submit_content.is_enabled()
                )
            )

            try:
                submit_content.click()
                print("Submit clicked using Selenium (content XPath).")
            except Exception as error:
                print(
                    "Submit content click failed; trying parent UI5 button:",
                    repr(error),
                )

                submit_parent_xpath = '//*[@id="__button3"]'

                try:
                    submit_parent = WebDriverWait(
                        self.driver,
                        10,
                    ).until(
                        EC.visibility_of_element_located(
                            (By.XPATH, submit_parent_xpath)
                        )
                    )

                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center', inline:'center'});",
                        submit_parent,
                    )

                    try:
                        submit_parent.click()
                        print("Submit clicked using parent UI5 button.")
                    except Exception as parent_error:
                        print(
                            "Submit parent click failed; using JavaScript:",
                            repr(parent_error),
                        )

                        submit_parent = self.driver.find_element(
                            By.XPATH,
                            submit_parent_xpath,
                        )
                        self.driver.execute_script(
                            "arguments[0].click();",
                            submit_parent,
                        )
                        print("Submit clicked using parent JavaScript.")

                except Exception as fallback_error:
                    print(
                        "Submit fallback failed:",
                        repr(fallback_error),
                    )
                    return False

            print("Search Criteria Submit clicked successfully.")

        except TimeoutException:
            print(
                "Submit button was not found or not clickable:",
                submit_xpath,
            )
            return False

        except Exception as error:
            print(
                "Submit button click failed:",
                repr(error),
            )
            return False

        # -------------------------------------------------------------
        # STEP 18: AFTER SUBMIT -> PENDING INVOICE -> ATTACHMENT
        # -------------------------------------------------------------
        # Required flow from the current Mahindra page:
        #
        #   Submit
        #      ↓
        #   Pending Invoice
        #      ↓
        #   Pending Invoice row
        #      ↓
        #   Upload Invoice directly
        #
        # Exact current DOM:
        #   Pending Invoice:
        #       //*[@id="__button1"]
        #
        #   Attachment icon:
        #       //*[@id="__xmlview0--idAttachment-icon"]
        #
        # Re-find both controls because SAP UI5 can re-render the toolbar
        # after Submit / Pending Invoice.
        if not self._process_all_pending_invoices(timeout=40):
            print("=" * 70)
            print("PENDING INVOICE / ATTACHMENT FLOW FAILED")
            print("=" * 70)
            return False

        # Give SAP/UI5 time to finish opening the attachment/details area.
        time.sleep(1)

        print("=" * 70)
        print("DOC UPLOAD SEARCH SUBMITTED SUCCESSFULLY")
        print(
            "Date range:",
            from_date.strftime("%d-%m-%Y"),
            "to",
            today.strftime("%d-%m-%Y"),
        )
        print("Type: Material")
        print("=" * 70)

        return True

    def _get_ds_invoice_path_from_db(self):
        """Read DS_INVOICE_PATH dynamically from dbo.SETTINGS."""
        connection = None
        cursor = None
        try:
            print("Loading DS_INVOICE_PATH from dbo.SETTINGS...")
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT TOP 1 DS_INVOICE_PATH
                FROM dbo.SETTINGS
                WHERE DS_INVOICE_PATH IS NOT NULL
                  AND LTRIM(RTRIM(DS_INVOICE_PATH)) <> ''
                ORDER BY ID DESC
                """
            )
            row = cursor.fetchone()
            if not row:
                print("DS_INVOICE_PATH not found in dbo.SETTINGS.")
                return None

            path_value = str(row[0] or '').strip()
            path_value = path_value.strip('"').strip("'").strip()
            path_value = os.path.expandvars(path_value)

            if not path_value:
                print("DS_INVOICE_PATH is empty in dbo.SETTINGS.")
                return None

            print("DS_INVOICE_PATH:", path_value)
            return path_value
        except Exception as error:
            print("Could not load DS_INVOICE_PATH:", repr(error))
            return None
        finally:
            try:
                if cursor is not None:
                    cursor.close()
            except Exception:
                pass
            try:
                if connection is not None:
                    connection.close()
            except Exception:
                pass

    def _find_invoice_file(self, invoice_no, folder_path):
        """
        Find ONLY the ORIGINAL invoice PDF for the selected Mahindra Invoice No.

        Example:
            Invoice No:
                P26400230

            Files in DS_INVOICE_PATH:
                P26400230DUPLICATEINVOICE.pdf
                P26400230EXTRAINVOICE.pdf
                P26400230ORIGINALINVOICE.pdf
                P26400230TRIPLICATEINVOICE.pdf

            Selected:
                P26400230ORIGINALINVOICE.pdf

        Important:
            DUPLICATE, EXTRA and TRIPLICATE invoice copies are ignored.
            The automation will upload only ORIGINALINVOICE.pdf.
        """
        if not invoice_no or not folder_path:
            return None

        folder_path = os.path.normpath(
            os.path.expandvars(
                str(folder_path).strip().strip('"').strip("'")
            )
        )

        if not os.path.isdir(folder_path):
            print(
                "DS_INVOICE_PATH does not exist or is not a folder:",
                folder_path,
            )
            return None

        invoice_key = str(invoice_no).strip().lower()

        if not invoice_key:
            print("Invoice No is empty.")
            return None

        # Exact expected ORIGINAL filename.
        #
        # Example:
        #   P26400230ORIGINALINVOICE.pdf
        #
        expected_original_stem = f"{invoice_key}originalinvoice"

        exact_original_candidates = []
        normalized_original_candidates = []

        print("=" * 70)
        print("SEARCHING ORIGINAL INVOICE ONLY")
        print("Invoice No :", invoice_no)
        print("Folder     :", folder_path)
        print(
            "Expected   :",
            f"{invoice_no}ORIGINALINVOICE.pdf",
        )
        print("=" * 70)

        try:
            # Search recursively because invoice folders can contain subfolders.
            for root, _, filenames in os.walk(folder_path):
                for filename in filenames:
                    if os.path.splitext(filename)[1].lower() != ".pdf":
                        continue

                    stem = os.path.splitext(filename)[0].strip().lower()

                    # ---------------------------------------------------------
                    # 1. FIRST PRIORITY: EXACT ORIGINAL FILENAME
                    # ---------------------------------------------------------
                    #
                    # P26400230ORIGINALINVOICE.pdf
                    #
                    if stem == expected_original_stem:
                        full_path = os.path.join(root, filename)

                        if os.path.isfile(full_path):
                            try:
                                modified_time = os.path.getmtime(full_path)
                            except OSError:
                                modified_time = 0

                            exact_original_candidates.append(
                                (modified_time, full_path)
                            )

                            print(
                                "EXACT ORIGINAL invoice found:",
                                full_path,
                            )

                        continue

                    # ---------------------------------------------------------
                    # 2. SAFE FALLBACK FOR SEPARATORS
                    # ---------------------------------------------------------
                    #
                    # Also allow:
                    #   P26400230_ORIGINALINVOICE.pdf
                    #   P26400230-ORIGINALINVOICE.pdf
                    #   P26400230 ORIGINALINVOICE.pdf
                    #
                    # This fallback still requires the complete
                    # InvoiceNo + ORIGINALINVOICE combination.
                    # It does NOT accept DUPLICATE / EXTRA / TRIPLICATE.
                    # ---------------------------------------------------------
                    normalized_stem = re.sub(
                        r"[^a-z0-9]+",
                        "",
                        stem,
                    )

                    if normalized_stem != expected_original_stem:
                        continue

                    full_path = os.path.join(root, filename)

                    if not os.path.isfile(full_path):
                        continue

                    try:
                        modified_time = os.path.getmtime(full_path)
                    except OSError:
                        modified_time = 0

                    normalized_original_candidates.append(
                        (modified_time, full_path)
                    )

                    print(
                        "ORIGINAL invoice candidate found:",
                        full_path,
                    )

        except Exception as error:
            print(
                "Original invoice search failed:",
                repr(error),
            )
            return None

        # -------------------------------------------------------------
        # SELECT EXACT ORIGINAL FIRST
        # -------------------------------------------------------------
        candidates = (
            exact_original_candidates
            if exact_original_candidates
            else normalized_original_candidates
        )

        if not candidates:
            print("=" * 70)
            print(
                f"ORIGINAL invoice PDF NOT FOUND for Invoice No: "
                f"{invoice_no}"
            )
            print(
                "Expected filename:",
                f"{invoice_no}ORIGINALINVOICE.pdf",
            )
            print(
                "Duplicate / Extra / Triplicate files were ignored."
            )
            print("=" * 70)
            return None

        # If more than one ORIGINAL exists, select the newest ORIGINAL only.
        selected = max(
            candidates,
            key=lambda item: item[0],
        )[1]

        if not os.path.isfile(selected):
            print(
                "Selected ORIGINAL invoice file does not exist:",
                selected,
            )
            return None

        print("=" * 70)
        print("ORIGINAL INVOICE SELECTED")
        print("Invoice No :", invoice_no)
        print("File       :", selected)
        print("=" * 70)

        return selected

    def _get_pending_status_elements(self):
        """Return visible SAP status elements whose text is exactly/contains Pending."""
        if self.driver is None:
            return []

        status_xpath = (
            '//*[starts-with(@id,"__status0-__xmlview0--list1-")]'
        )
        result = []

        try:
            elements = self.driver.find_elements(By.XPATH, status_xpath)
        except Exception as error:
            print("Could not read Pending status elements:", repr(error))
            return result

        for element in elements:
            try:
                if not element.is_displayed():
                    continue

                text = (element.text or "").strip()
                if re.search(r"\bPending\b", text, re.IGNORECASE) and not re.search(
                    r"\bDone\b", text, re.IGNORECASE
                ):
                    result.append(element)
            except (
                StaleElementReferenceException,
                NoSuchElementException,
            ):
                continue
            except Exception:
                continue

        return result

    def _get_pending_status_snapshot(self):
        """Return pending rows as fresh text/status references."""
        if self.driver is None:
            return []

        status_xpath = (
            '//*[starts-with(@id,"__status0-__xmlview0--list1-")]'
        )
        result = []

        try:
            elements = self.driver.find_elements(By.XPATH, status_xpath)
        except Exception as error:
            print("Pending status scan failed:", repr(error))
            return result

        for status in elements:
            try:
                if not status.is_displayed():
                    continue

                status_text = (status.text or "").strip()
                if not re.search(r"\bPending\b", status_text, re.IGNORECASE):
                    continue
                if re.search(r"\bDone\b", status_text, re.IGNORECASE):
                    continue

                row = None
                try:
                    row = status.find_element(By.XPATH, "ancestor::li[1]")
                except Exception:
                    pass

                if row is None:
                    try:
                        row = status.find_element(
                            By.XPATH,
                            "ancestor::*[self::div or self::tr][1]",
                        )
                    except Exception:
                        pass

                row_text = ""
                if row is not None:
                    try:
                        row_text = (row.text or "").replace("\n", " | ").strip()
                    except Exception:
                        row_text = ""

                invoice_match = re.search(
                    r"Invoice\s*:\s*([A-Za-z0-9_-]+)",
                    row_text,
                    re.IGNORECASE,
                )
                invoice_no = invoice_match.group(1).strip() if invoice_match else ""

                asn_match = re.search(
                    r"ASN\s*No\.?\s*[:.]?\s*([A-Za-z0-9_-]+)",
                    row_text,
                    re.IGNORECASE,
                )
                asn_no = asn_match.group(1).strip() if asn_match else ""

                result.append(
                    {
                        "status": status,
                        "row": row,
                        "status_text": status_text,
                        "row_text": row_text,
                        "invoice_no": invoice_no,
                        "asn_no": asn_no,
                    }
                )
            except (
                StaleElementReferenceException,
                NoSuchElementException,
            ):
                continue
            except Exception:
                continue

        return result

    def _click_element_safe(self, element):
        """Click a UI5 element with Selenium first and JS as fallback."""
        if self.driver is None or element is None:
            return False

        try:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center',inline:'center'});",
                element,
            )
        except Exception:
            pass

        try:
            element.click()
            return True
        except Exception as error:
            print("Normal click failed:", repr(error))

        try:
            self.driver.execute_script("arguments[0].click();", element)
            return True
        except Exception as error:
            print("JavaScript click failed:", repr(error))
            return False

    def _wait_for_invoice_status_change(self, invoice_no, timeout=45):
        """Wait until the uploaded invoice is no longer Pending."""
        if self.driver is None:
            return False

        invoice_no = str(invoice_no or "").strip()
        end_time = time.time() + timeout

        print(
            f"Waiting for Invoice {invoice_no} status to change from Pending..."
        )

        while time.time() < end_time:
            if self._stop_event.is_set():
                return False

            try:
                snapshots = self._get_pending_status_snapshot()
                matching_pending = []

                for item in snapshots:
                    if invoice_no and invoice_no.lower() in item["row_text"].lower():
                        matching_pending.append(item)

                if not matching_pending:
                    # Re-read all visible rows. If the invoice is now Done,
                    # or it disappeared because the Pending filter refreshed,
                    # the upload is complete.
                    all_rows_xpath = (
                        '//*[starts-with(@id,"__item2-__xmlview0--list1-")]'
                    )
                    rows = self.driver.find_elements(By.XPATH, all_rows_xpath)
                    found_invoice = False
                    invoice_done = False

                    for row in rows:
                        try:
                            if not row.is_displayed():
                                continue
                            text = (row.text or "").replace("\n", " | ").strip()
                            if invoice_no.lower() not in text.lower():
                                continue
                            found_invoice = True
                            if re.search(r"\bDone\b", text, re.IGNORECASE):
                                invoice_done = True
                                break
                        except Exception:
                            continue

                    if invoice_done:
                        print(
                            f"Invoice {invoice_no}: status changed to Done."
                        )
                        return True

                    if not found_invoice:
                        print(
                            f"Invoice {invoice_no}: removed from Pending list; "
                            "treating upload as completed."
                        )
                        return True

            except Exception as error:
                print("Status-change check warning:", repr(error))

            time.sleep(1.0)

        print(
            f"Invoice {invoice_no} is still Pending after {timeout} seconds."
        )
        return False

    def _upload_invoice_for_pending_asn(self, pending_item, timeout=40, open_attachment=False):
        """Upload one Pending ASN invoice.

        First ASN: open the Attachment panel once.
        Next ASNs: keep the existing Attachment panel open and click
        Upload Invoice directly. Never toggle the Attachment icon again.
        """
        if self.driver is None:
            return False

        invoice_no = str(pending_item.get("invoice_no") or "").strip()
        asn_no = str(pending_item.get("asn_no") or "").strip()

        if not invoice_no:
            print(
                "ERROR: Invoice No could not be extracted from Pending row:",
                pending_item.get("row_text", ""),
            )
            return False

        print("=" * 70)
        print("PROCESSING ONE PENDING ASN")
        print("ASN No     :", asn_no)
        print("Invoice No :", invoice_no)
        print("=" * 70)

        # -------------------------------------------------------------
        # 1. CLICK THE ACTUAL PENDING STATUS TEXT
        # -------------------------------------------------------------
        status_xpath = (
            '//*[starts-with(@id,"__status0-__xmlview0--list1-")]'
            '[contains(normalize-space(.),"Pending")]'
        )

        status_element = None
        try:
            # Prefer the exact status element captured during the scan.
            status_element = pending_item.get("status")
            if status_element is not None and not status_element.is_displayed():
                status_element = None
        except Exception:
            status_element = None

        if status_element is None:
            try:
                status_element = WebDriverWait(self.driver, timeout).until(
                    EC.visibility_of_element_located((By.XPATH, status_xpath))
                )
            except Exception as error:
                print("Pending status text not found:", repr(error))
                return False

        print("Clicking Pending status text for Invoice:", invoice_no)
        if not self._click_element_safe(status_element):
            return False

        time.sleep(0.8)

        # -------------------------------------------------------------
        # 2. OPEN ATTACHMENT PANEL ONLY FOR THE FIRST ASN
        # -------------------------------------------------------------
        # FIRST ASN:
        #     Pending row -> Attachment icon -> Upload Invoice
        #
        # NEXT ASNs:
        #     Pending row -> Upload Invoice
        #
        # IMPORTANT:
        # The Attachment icon is a toggle. Once the panel is open, clicking
        # it again closes the panel. Therefore it MUST be clicked only once,
        # for the first ASN of this processing run.
        # -------------------------------------------------------------
        attachment_xpath = '//*[@id="__xmlview0--idAttachment-icon"]'

        if open_attachment:
            try:
                attachment = WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable((By.XPATH, attachment_xpath))
                )

                if not self._click_element_safe(attachment):
                    print("First ASN: Attachment click failed.")
                    return False

                print("FIRST ASN: Attachment panel opened.")
                time.sleep(0.8)

            except Exception as error:
                print("FIRST ASN: Attachment click failed:", repr(error))
                return False
        else:
            print(
                "NEXT ASN: Attachment panel is already open. "
                "Skipping Attachment icon."
            )
            time.sleep(0.5)

        # -------------------------------------------------------------
        # 3. CLICK UPLOAD INVOICE
        # -------------------------------------------------------------
        upload_xpaths = [
            '//*[@id="__xmlview0--idBtnIA-BDI-content"]',
            '//*[@id="__xmlview0--idBtnIA-content"]',
        ]

        upload_button = None
        for upload_xpath in upload_xpaths:
            try:
                upload_button = WebDriverWait(self.driver, 8).until(
                    EC.element_to_be_clickable((By.XPATH, upload_xpath))
                )
                if upload_button is not None:
                    print("Upload Invoice button found:", upload_xpath)
                    break
            except Exception:
                upload_button = None

        if upload_button is None:
            print("Upload Invoice button was not found.")
            return False

        if not self._click_element_safe(upload_button):
            return False

        print("Upload Invoice clicked.")

        # -------------------------------------------------------------
        # 4. WAIT FOR FILE ATTACHMENT MODAL
        # -------------------------------------------------------------
        dialog_xpath = '//*[@id="__dialog3"]'
        try:
            dialog = WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((By.XPATH, dialog_xpath))
            )
            print("File Attachment modal opened: __dialog3")
        except Exception as error:
            print("File Attachment modal was not found:", repr(error))
            return False

        # -------------------------------------------------------------
        # 5. GET DS_INVOICE_PATH AND FIND INVOICE PDF
        # -------------------------------------------------------------
        ds_invoice_path = self._get_ds_invoice_path_from_db()
        if not ds_invoice_path:
            print("Cannot upload invoice: DS_INVOICE_PATH is missing.")
            return False

        invoice_file = self._find_invoice_file(
            invoice_no,
            ds_invoice_path,
        )
        if not invoice_file:
            print(
                f"Cannot upload Invoice {invoice_no}: ORIGINAL invoice PDF not found."
            )
            return False

        # -------------------------------------------------------------
        # 6. SELECT FILE USING __hbox0
        # -------------------------------------------------------------
        file_container_xpath = '//*[@id="__hbox0"]'
        file_input = None

        try:
            file_container = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, file_container_xpath))
            )

            # __hbox0 is the SAP container. The real input[type=file] is
            # normally a child of this container.
            try:
                file_input = file_container.find_element(
                    By.XPATH,
                    './/input[@type="file"]',
                )
            except Exception:
                pass

            if file_input is None:
                # Some UI5 versions place the file input one level around the
                # hbox. Search nearby before failing.
                try:
                    file_input = file_container.find_element(
                        By.XPATH,
                        './/input',
                    )
                except Exception:
                    pass

            if file_input is None:
                # User supplied __hbox0 as the file-input area. If it itself is
                # an input, use it directly.
                tag_name = (file_container.tag_name or '').lower()
                if tag_name == 'input':
                    file_input = file_container

            if file_input is None:
                print(
                    "File input not found inside __hbox0. "
                    "Container XPath:",
                    file_container_xpath,
                )
                return False

            # Selenium can set an HTML file input directly without opening the
            # Windows File Explorer dialog.
            file_input.send_keys(os.path.abspath(invoice_file))
            print("Invoice PDF path passed to file input:", invoice_file)

            # Verify selection when the browser exposes the value.
            try:
                selected_value = file_input.get_attribute("value") or ""
                print("File input value:", selected_value)
            except Exception:
                pass

        except Exception as error:
            print("Invoice file selection failed:", repr(error))
            return False

        # -------------------------------------------------------------
        # 7. CHECK DIGITAL SIGNATURE DECLARATION
        # -------------------------------------------------------------
        # SAP UI5 CHECKBOX
        #
        # IMPORTANT:
        # The <input id="id_Check1-CB"> is NOT the safest element to
        # click in this SAP UI5 control. It is wrapped by the UI5
        # checkbox control and can be hidden/custom handled.
        #
        # The reliable click target from the supplied DOM is:
        #
        #     //*[@id="id_Check1-label"]
        #
        # We therefore click the LABEL first and then verify that SAP
        # UI5 changed:
        #
        #     aria-checked="false" -> "true"
        #     sapMCbMark          -> sapMCbMarkChecked
        #     input checked       -> checked
        #
        # Only after SAP UI5 reports checked=true do we continue to
        # Submit Document.
        # -------------------------------------------------------------

        checkbox_control_xpath = '//*[@id="id_Check1"]'
        checkbox_label_xpath = '//*[@id="id_Check1-label"]'
        checkbox_bg_xpath = '//*[@id="id_Check1-CbBg"]'
        checkbox_input_xpath = '//*[@id="id_Check1-CbBg"]//input[@id="id_Check1-CB"]'

        try:
            print("=" * 70)
            print("CHECKING DIGITAL-SIGNATURE CHECKBOX")
            print("=" * 70)

            def get_checkbox_state():
                """
                Return the current SAP UI5 checkbox state.

                The authoritative state is aria-checked on id_Check1.
                The native input and visual UI5 class are used as
                additional diagnostics/fallback verification.
                """
                try:
                    control = self.driver.find_element(
                        By.XPATH,
                        checkbox_control_xpath,
                    )

                    aria_checked = (
                        control.get_attribute("aria-checked") or ""
                    ).strip().lower()

                    try:
                        input_element = self.driver.find_element(
                            By.XPATH,
                            checkbox_input_xpath,
                        )
                        input_selected = input_element.is_selected()
                        input_checked = (
                            input_element.get_attribute("checked") or ""
                        ).strip().lower()
                    except Exception:
                        input_selected = False
                        input_checked = ""

                    try:
                        bg_element = self.driver.find_element(
                            By.XPATH,
                            checkbox_bg_xpath,
                        )
                        bg_class = (
                            bg_element.get_attribute("class") or ""
                        ).lower()
                    except Exception:
                        bg_class = ""

                    return {
                        "aria": aria_checked,
                        "input_selected": input_selected,
                        "input_checked": input_checked,
                        "bg_checked": "sapmcbmarkchecked" in bg_class,
                    }

                except Exception:
                    return {
                        "aria": "",
                        "input_selected": False,
                        "input_checked": "",
                        "bg_checked": False,
                    }

            def checkbox_is_checked():
                state = get_checkbox_state()

                # SAP UI5's own state is the primary verification.
                if state["aria"] == "true":
                    return True

                # These are only secondary confirmations.
                if state["input_selected"]:
                    return True

                if state["input_checked"] in ("checked", "true"):
                    return True

                if state["bg_checked"]:
                    return True

                return False

            # ---------------------------------------------------------
            # Wait until the checkbox exists.
            # ---------------------------------------------------------
            WebDriverWait(
                self.driver,
                20,
            ).until(
                EC.presence_of_element_located(
                    (By.XPATH, checkbox_control_xpath)
                )
            )

            # Give SAP UI5 a moment to finish rendering the label.
            WebDriverWait(
                self.driver,
                10,
            ).until(
                EC.visibility_of_element_located(
                    (By.XPATH, checkbox_label_xpath)
                )
            )

            print("Initial checkbox state:", get_checkbox_state())

            # ---------------------------------------------------------
            # NEVER click an already checked checkbox.
            # ---------------------------------------------------------
            if checkbox_is_checked():
                print("Digital-signature checkbox is already CHECKED.")

            else:
                print("Digital-signature checkbox is UNCHECKED.")
                print(
                    "Primary click target:",
                    checkbox_label_xpath,
                )

                clicked = False

                # -----------------------------------------------------
                # METHOD 1 - CLICK THE LABEL
                #
                # This is the exact element visible in the supplied
                # before/after DOM and is the preferred SAP UI5 action.
                # -----------------------------------------------------
                try:
                    label = WebDriverWait(
                        self.driver,
                        10,
                    ).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, checkbox_label_xpath)
                        )
                    )

                    self.driver.execute_script(
                        """
                        arguments[0].scrollIntoView({
                            block: 'center',
                            inline: 'center'
                        });
                        """,
                        label,
                    )

                    time.sleep(0.3)

                    label.click()
                    clicked = True

                    print(
                        "SUCCESS: id_Check1-label clicked with Selenium."
                    )

                except Exception as error:
                    print(
                        "Label Selenium click failed:",
                        repr(error),
                    )

                # -----------------------------------------------------
                # Wait for SAP UI5 to process the label click.
                # -----------------------------------------------------
                if clicked:
                    try:
                        WebDriverWait(
                            self.driver,
                            5,
                        ).until(
                            lambda d: checkbox_is_checked()
                        )

                        print(
                            "SUCCESS: SAP UI5 checkbox changed to CHECKED."
                        )

                    except TimeoutException:
                        print(
                            "Label was clicked, but SAP UI5 state "
                            "did not change. Trying parent control."
                        )

                # -----------------------------------------------------
                # METHOD 2 - CLICK THE SAP UI5 PARENT CONTROL
                # -----------------------------------------------------
                if not checkbox_is_checked():
                    try:
                        control = WebDriverWait(
                            self.driver,
                            10,
                        ).until(
                            EC.visibility_of_element_located(
                                (By.XPATH, checkbox_control_xpath)
                            )
                        )

                        self.driver.execute_script(
                            """
                            arguments[0].scrollIntoView({
                                block: 'center',
                                inline: 'center'
                            });
                            """,
                            control,
                        )

                        time.sleep(0.2)

                        control.click()

                        print(
                            "SAP UI5 parent checkbox clicked:"
                            " //*[@id='id_Check1']"
                        )

                    except Exception as error:
                        print(
                            "Parent checkbox Selenium click failed:",
                            repr(error),
                        )

                # -----------------------------------------------------
                # METHOD 3 - CLICK THE VISUAL CbBg
                #
                # This is a fallback only. Do NOT use it first because
                # the label/parent is the proper UI5 interaction target.
                # -----------------------------------------------------
                if not checkbox_is_checked():
                    try:
                        checkbox_bg = WebDriverWait(
                            self.driver,
                            10,
                        ).until(
                            EC.visibility_of_element_located(
                                (By.XPATH, checkbox_bg_xpath)
                            )
                        )

                        self.driver.execute_script(
                            """
                            arguments[0].scrollIntoView({
                                block: 'center',
                                inline: 'center'
                            });
                            """,
                            checkbox_bg,
                        )

                        time.sleep(0.2)

                        checkbox_bg.click()

                        print(
                            "SAP UI5 CbBg clicked:"
                            " //*[@id='id_Check1-CbBg']"
                        )

                    except Exception as error:
                        print(
                            "CbBg Selenium click failed:",
                            repr(error),
                        )

                # -----------------------------------------------------
                # METHOD 4 - JS click ON THE LABEL
                #
                # Important: JS click is performed on the LABEL, not
                # directly on the hidden native input.
                # -----------------------------------------------------
                if not checkbox_is_checked():
                    try:
                        label = self.driver.find_element(
                            By.XPATH,
                            checkbox_label_xpath,
                        )

                        self.driver.execute_script(
                            """
                            arguments[0].click();
                            """,
                            label,
                        )

                        print(
                            "JavaScript click executed on id_Check1-label."
                        )

                    except Exception as error:
                        print(
                            "JavaScript label click failed:",
                            repr(error),
                        )

                # -----------------------------------------------------
                # METHOD 5 - Dispatch mouse events on the UI5 control.
                # -----------------------------------------------------
                if not checkbox_is_checked():
                    try:
                        control = self.driver.find_element(
                            By.XPATH,
                            checkbox_control_xpath,
                        )

                        self.driver.execute_script(
                            """
                            const el = arguments[0];

                            ['mousedown', 'mouseup', 'click'].forEach(
                                function(eventName) {
                                    el.dispatchEvent(
                                        new MouseEvent(
                                            eventName,
                                            {
                                                bubbles: true,
                                                cancelable: true,
                                                view: window
                                            }
                                        )
                                    );
                                }
                            );
                            """,
                            control,
                        )

                        print(
                            "UI5 mouse events dispatched to id_Check1."
                        )

                    except Exception as error:
                        print(
                            "UI5 mouse-event fallback failed:",
                            repr(error),
                        )

                # -----------------------------------------------------
                # FINAL SAP UI5 VERIFICATION
                # -----------------------------------------------------
                try:
                    WebDriverWait(
                        self.driver,
                        10,
                    ).until(
                        lambda d: (
                            str(
                                d.find_element(
                                    By.XPATH,
                                    checkbox_control_xpath,
                                ).get_attribute(
                                    "aria-checked"
                                ) or ""
                            ).strip().lower()
                            == "true"
                        )
                    )

                    print("=" * 70)
                    print(
                        "SUCCESS: Digital-signature checkbox is CHECKED."
                    )
                    print(
                        "Final checkbox state:",
                        get_checkbox_state(),
                    )
                    print("=" * 70)

                except TimeoutException:
                    state = get_checkbox_state()

                    print("=" * 70)
                    print(
                        "ERROR: CHECKBOX WAS NOT CHECKED."
                    )
                    print(
                        "Final aria-checked:",
                        state["aria"],
                    )
                    print(
                        "Final input selected:",
                        state["input_selected"],
                    )
                    print(
                        "Final input checked:",
                        state["input_checked"],
                    )
                    print(
                        "Final CbBg class checked:",
                        state["bg_checked"],
                    )
                    print("=" * 70)

                    # SAFETY STOP:
                    # Never submit the document while SAP UI5 reports
                    # aria-checked=false.
                    return False

            # ---------------------------------------------------------
            # FINAL SAFETY CHECK
            # ---------------------------------------------------------
            final_state = get_checkbox_state()

            if final_state["aria"] != "true":
                print(
                    "SAFETY STOP: SAP UI5 checkbox is not "
                    "aria-checked=true."
                )
                print("Current state:", final_state)
                return False

            print(
                "Digital-signature checkbox verified:",
                final_state,
            )

        except Exception as error:
            print(
                "Digital-signature checkbox handling failed:",
                repr(error),
            )
            return False

        # -------------------------------------------------------------
        # -------------------------------------------------------------
        # 8. CLICK SUBMIT DOCUMENT
        # -------------------------------------------------------------
        # Submit ONLY after the digital-signature checkbox has been
        # verified as checked.
        submit_document_xpath = '//*[@id="__button10-inner"]'

        try:
            print("Waiting for Submit Document...")

            submit_document = WebDriverWait(
                self.driver,
                timeout,
            ).until(
                EC.visibility_of_element_located(
                    (By.XPATH, submit_document_xpath)
                )
            )

            try:
                self.driver.execute_script(
                    """
                    arguments[0].scrollIntoView({
                        block: 'center',
                        inline: 'center'
                    });
                    """,
                    submit_document,
                )
            except Exception:
                pass

            WebDriverWait(
                self.driver,
                10,
            ).until(
                lambda d:
                    submit_document.is_displayed()
                    and submit_document.is_enabled()
            )

            time.sleep(0.3)

            try:
                submit_document.click()
                print("Submit Document clicked successfully.")
            except Exception as error:
                print(
                    "Normal Submit Document click failed:",
                    repr(error),
                )

                submit_document = self.driver.find_element(
                    By.XPATH,
                    submit_document_xpath,
                )

                self.driver.execute_script(
                    "arguments[0].click();",
                    submit_document,
                )

                print(
                    "Submit Document JavaScript click completed."
                )

        except Exception as error:
            print(
                "Submit Document handling failed:",
                repr(error),
            )
            return False

        # -------------------------------------------------------------
        # 9. WAIT FOR FILE ATTACHMENT MODAL TO CLOSE
        # -------------------------------------------------------------
        try:
            WebDriverWait(self.driver, 20).until(
                EC.invisibility_of_element_located(
                    (By.XPATH, dialog_xpath)
                )
            )
            print("File Attachment modal closed.")

        except Exception:
            print(
                "File Attachment modal close wait timed out."
            )

        # -------------------------------------------------------------
        # 10. HANDLE SUCCESS POPUP
        # -------------------------------------------------------------
        # After Submit Document, Mahindra shows:
        #
        #   Success
        #   INV_<ASN>PDF.PDF : has been linked with ASN: <ASN>
        #   OK
        #
        # Current OK button XPath:
        #
        #   //*[@id="__mbox-btn-0"]
        #
        # IMPORTANT:
        # The OK popup must be closed BEFORE starting the next Pending
        # ASN. Otherwise the popup can block the Pending Invoice button.
        success_ok_xpath = '//*[@id="__mbox-btn-0"]'

        try:
            print("Waiting for Mahindra Success popup...")

            # First try the current stable XPath.
            success_ok_button = None
            try:
                success_ok_button = WebDriverWait(
                    self.driver,
                    20,
                ).until(
                    EC.visibility_of_element_located(
                        (By.XPATH, success_ok_xpath)
                    )
                )
            except Exception:
                pass

            # Fallback: find the visible OK button by its actual text.
            # This handles SAP/UI5 cases where __mbox-btn-0 changes.
            if success_ok_button is None:
                ok_candidates = self.driver.find_elements(
                    By.XPATH,
                    "//button | //*[@role='button'] | "
                    "//input[@type='button'] | //input[@type='submit']"
                )

                for candidate in ok_candidates:
                    try:
                        if not candidate.is_displayed():
                            continue

                        label = (
                            candidate.text
                            or candidate.get_attribute("value")
                            or candidate.get_attribute("aria-label")
                            or candidate.get_attribute("title")
                            or ""
                        ).strip().lower()

                        if label == "ok":
                            success_ok_button = candidate
                            break
                    except Exception:
                        continue

            if success_ok_button is None:
                print("SUCCESS popup detected/waited for, but OK button was not found.")
                return False

            print("Success popup detected. Clicking OK.")

            try:
                self.driver.execute_script(
                    """
                    arguments[0].scrollIntoView({
                        block: 'center',
                        inline: 'center'
                    });
                    """,
                    success_ok_button,
                )
            except Exception:
                pass

            try:
                WebDriverWait(
                    self.driver,
                    10,
                ).until(
                    lambda d:
                        success_ok_button.is_displayed()
                        and success_ok_button.is_enabled()
                )
            except Exception:
                pass

            # Normal Selenium click first.
            try:
                success_ok_button.click()
                print("Success popup OK clicked successfully.")
            except Exception as error:
                print(
                    "Normal Success popup OK click failed:",
                    repr(error),
                )

                # Re-find the visible OK button because SAP UI5 can re-render it.
                success_ok_button = None
                ok_candidates = self.driver.find_elements(
                    By.XPATH,
                    "//button | //*[@role='button'] | "
                    "//input[@type='button'] | //input[@type='submit']"
                )

                for candidate in ok_candidates:
                    try:
                        if not candidate.is_displayed():
                            continue

                        label = (
                            candidate.text
                            or candidate.get_attribute("value")
                            or candidate.get_attribute("aria-label")
                            or candidate.get_attribute("title")
                            or ""
                        ).strip().lower()

                        if label == "ok":
                            success_ok_button = candidate
                            break
                    except Exception:
                        continue

                if success_ok_button is None:
                    print("Could not re-find Success popup OK button.")
                    return False

                self.driver.execute_script(
                    "arguments[0].click();",
                    success_ok_button,
                )
                print("Success popup OK clicked using JavaScript.")

            # ---------------------------------------------------------
            # VERIFY THAT THE SUCCESS POPUP IS CLOSED
            # ---------------------------------------------------------
            try:
                WebDriverWait(
                    self.driver,
                    15,
                ).until(
                    lambda d: not any(
                        element.is_displayed()
                        for element in d.find_elements(
                            By.XPATH,
                            "//button | //*[@role='button'] | "
                            "//input[@type='button'] | //input[@type='submit']"
                        )
                        if (
                            (
                                element.text
                                or element.get_attribute("value")
                                or element.get_attribute("aria-label")
                                or element.get_attribute("title")
                                or ""
                            ).strip().lower() == "ok"
                        )
                    )
                )

                print(
                    "Success popup closed. "
                    "Ready for next Pending ASN."
                )

            except Exception:
                # Also verify the original XPath is no longer visible.
                try:
                    WebDriverWait(
                        self.driver,
                        5,
                    ).until(
                        EC.invisibility_of_element_located(
                            (By.XPATH, success_ok_xpath)
                        )
                    )
                    print(
                        "Success popup closed using XPath verification. "
                        "Ready for next Pending ASN."
                    )
                except Exception:
                    print(
                        "WARNING: Success popup OK was clicked, "
                        "but popup close could not be verified."
                    )
                    return False

        except Exception as error:
            print(
                "SUCCESS popup / OK button handling failed:",
                repr(error),
            )

            # SAFETY STOP:
            # Never start the next ASN while the Success popup may still
            # be blocking the page.
            return False

        # -------------------------------------------------------------
        # 11. SUCCESS POPUP IS THE UPLOAD COMPLETION SIGNAL
        # -------------------------------------------------------------
        # The Success popup says:
        #
        #   <invoice PDF> : has been linked with ASN: <ASN>
        #
        # Once this popup has been successfully acknowledged, the upload
        # operation is complete. Do NOT wait for the old Pending row to
        # change in the same DOM.
        #
        # The previous implementation called
        # _wait_for_invoice_status_change() here. On this SAP/UI5 page the
        # Pending list can keep a stale status element even after the row
        # visibly changes to Done. That caused the automation to wait 45
        # seconds and STOP instead of processing the next Pending ASN.
        #
        # The main Pending loop will now re-click the Pending Invoice filter,
        # obtain a fresh snapshot, select the next Pending ASN, and continue.
        # -------------------------------------------------------------
        time.sleep(1.0)

        print("=" * 70)
        print("ONE PENDING ASN COMPLETED")
        print("Success popup acknowledged.")
        print("ASN No     :", asn_no)
        print("Invoice No :", invoice_no)
        print("Starting next Pending ASN...")
        print("=" * 70)

        return True

    def _process_all_pending_invoices(self, timeout=40):
        """
        Process Pending Invoice rows ONE BY ONE.

        Required business flow:

            FIRST Pending ASN
                -> click Pending status text
                -> Attachment icon (ONCE)
                -> Upload Invoice
                -> Success popup
                -> click OK

            NEXT Pending ASN(s)
                -> click Pending status text
                -> DO NOT click Attachment icon
                -> Upload Invoice directly
                -> Success popup
                -> click OK
                -> __dialog3
                -> invoice PDF from DS_INVOICE_PATH
                -> digital-signature checkbox
                -> Submit Document
                -> wait for Done
                -> Pending Invoice again
                -> next Pending ASN

        The automation stops only when no Pending row remains. If an upload
        fails or the status does not become Done, it stops safely and does not
        process the same invoice again.
        """
        if self.driver is None:
            print("Pending invoice processing: Edge driver unavailable.")
            return False

        pending_button_xpath = '//*[@id="__button1"]'
        processed_invoices = set()
        iteration = 0

        print("=" * 70)
        print("STARTING ONE-BY-ONE PENDING INVOICE PROCESSING")
        print("=" * 70)

        while not self._stop_event.is_set():
            iteration += 1
            if iteration > 200:
                print("Safety stop: more than 200 Pending processing iterations.")
                return False

            # ---------------------------------------------------------
            # CLICK PENDING INVOICE FILTER AGAIN FOR EVERY NEXT ASN
            # ---------------------------------------------------------
            try:
                pending_button = WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable((By.XPATH, pending_button_xpath))
                )
                if not self._click_element_safe(pending_button):
                    print("Could not click Pending Invoice filter.")
                    return False
                print(f"Pending Invoice filter clicked - iteration #{iteration}.")
            except Exception as error:
                print("Pending Invoice button failed:", repr(error))
                return False

            time.sleep(0.8)

            # Give SAP/UI5 time to re-render the filtered list.
            time.sleep(0.8)
            pending_items = self._get_pending_status_snapshot()

            # Remove already successfully processed invoice numbers from the
            # current scan. This is another guard against stale UI5 rendering.
            available_items = []
            for item in pending_items:
                invoice_no = str(item.get("invoice_no") or "").strip()
                if invoice_no and invoice_no.lower() in {
                    value.lower() for value in processed_invoices
                }:
                    print(
                        "SKIP already processed invoice:",
                        invoice_no,
                    )
                    continue
                available_items.append(item)

            print(
                f"Pending rows found: {len(pending_items)} | "
                f"Available for processing: {len(available_items)}"
            )

            # ---------------------------------------------------------
            # NO PENDING LEFT -> AUTOMATION COMPLETE
            # ---------------------------------------------------------
            if not available_items:
                # A final fresh scan is intentionally performed before stop.
                time.sleep(1.0)
                final_items = self._get_pending_status_snapshot()
                final_available = []

                for item in final_items:
                    invoice_no = str(item.get("invoice_no") or "").strip()
                    if invoice_no and invoice_no.lower() in {
                        value.lower() for value in processed_invoices
                    }:
                        continue
                    final_available.append(item)

                if not final_available:
                    print("=" * 70)
                    print("ALL PENDING ASN INVOICES ARE COMPLETED.")
                    print("NO PENDING STATUS REMAINS.")
                    print("AUTOMATION STOPPED SUCCESSFULLY.")
                    print("=" * 70)
                    return True

                available_items = final_available

            # ---------------------------------------------------------
            # SELECT THE FIRST REAL PENDING ASN
            # ---------------------------------------------------------
            item = available_items[0]
            invoice_no = str(item.get("invoice_no") or "").strip()
            asn_no = str(item.get("asn_no") or "").strip()

            if not invoice_no:
                print(
                    "SAFETY STOP: Pending row has no Invoice No. Row text:",
                    item.get("row_text", ""),
                )
                return False

            if invoice_no.lower() in {
                value.lower() for value in processed_invoices
            }:
                print(
                    "SAFETY STOP: Same Invoice No appeared again:",
                    invoice_no,
                )
                return False

            print("=" * 70)
            print("NEXT PENDING ASN SELECTED")
            print("ASN No     :", asn_no)
            print("Invoice No :", invoice_no)
            print("Row        :", item.get("row_text", ""))
            print("=" * 70)

            # ---------------------------------------------------------
            # PROCESS EXACTLY ONE PENDING ASN
            # ---------------------------------------------------------
            if not self._upload_invoice_for_pending_asn(
                item,
                timeout=timeout,
                open_attachment=(iteration == 1),
            ):
                print("=" * 70)
                print("PENDING INVOICE PROCESSING FAILED.")
                print("Automation stopped safely.")
                print("Invoice:", invoice_no)
                print("=" * 70)
                return False

            processed_invoices.add(invoice_no)

            # Let SAP/UI5 finish changing Pending -> Done before the next scan.
            time.sleep(1.0)

        print("Pending invoice processing stopped by stop event.")
        return False

    def _click_pending_invoice_and_attachment(self, timeout=30):
        """Compatibility wrapper for existing callers.

        The old method only opened the first attachment. The new business flow
        must process every Pending ASN one by one, so delegate to the complete
        Pending Invoice workflow.
        """
        return self._process_all_pending_invoices(timeout=timeout)

    def _select_doc_upload_date(
        self,
        icon_xpath,
        target_date,
        label,
        timeout=20,
    ):
        """
        Select an exact date in Mahindra's UI5 DatePicker.

        The previous implementation depended mainly on data-sap-day. On the
        current Mahindra page the calendar can render without that attribute,
        so this method now uses several safe fallbacks:

            1. Open the requested date picker icon.
            2. Select exact data-sap-day when available.
            3. Select an exact aria/title date when available.
            4. Otherwise locate the DatePicker input belonging to the icon,
               enter the exact date, and fire UI5-compatible events.
            5. Verify that the field contains the requested date before
               returning True.

        This method is used for both:
            From Date = today - 2 days
            To Date   = today
        """
        if self.driver is None:
            return False

        target_key = target_date.strftime("%Y%m%d")
        target_ddmmyyyy = target_date.strftime("%d-%m-%Y")
        target_mmddyyyy = target_date.strftime("%m/%d/%Y")
        target_ddmmyyyy_slash = target_date.strftime("%d/%m/%Y")
        target_dot = target_date.strftime("%d.%m.%Y")
        target_iso = target_date.strftime("%Y-%m-%d")

        print(
            f"{label}: opening date picker for "
            f"{target_ddmmyyyy}"
        )

        # -------------------------------------------------------------
        # STEP 1: CLICK DATE-PICKER ICON
        # -------------------------------------------------------------
        try:
            icon = WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located(
                    (By.XPATH, icon_xpath)
                )
            )

            try:
                self.driver.execute_script(
                    """
                    arguments[0].scrollIntoView({
                        block: 'center',
                        inline: 'center'
                    });
                    """,
                    icon,
                )
            except Exception:
                pass

            try:
                icon.click()
            except Exception as click_error:
                print(
                    f"{label}: normal calendar click failed; "
                    f"using JavaScript:",
                    repr(click_error),
                )
                self.driver.execute_script(
                    "arguments[0].click();",
                    icon,
                )

            print(f"{label}: date picker opened.")

        except TimeoutException:
            print(
                f"{label}: date picker icon not found:",
                icon_xpath,
            )
            return False

        except Exception as error:
            print(
                f"{label}: date picker icon click failed:",
                repr(error),
            )
            return False

        # -------------------------------------------------------------
        # STEP 2: TRY UI5 CALENDAR EXACT DATE
        # -------------------------------------------------------------
        end_time = time.time() + timeout

        while time.time() < end_time:
            if self._stop_event.is_set():
                return False

            try:
                self.driver.switch_to.default_content()

                # ---------------------------------------------------------
                # 2A. Exact data-sap-day
                # ---------------------------------------------------------
                result = self.driver.execute_script(
                    """
                    const target = arguments[0];

                    const visible = (el) => {
                        if (!el) return false;

                        const s = getComputedStyle(el);
                        const r = el.getBoundingClientRect();

                        return (
                            s.display !== 'none' &&
                            s.visibility !== 'hidden' &&
                            r.width > 0 &&
                            r.height > 0
                        );
                    };

                    const days = Array.from(
                        document.querySelectorAll('[data-sap-day]')
                    ).filter(visible);

                    const exact = days.find(
                        el => el.getAttribute('data-sap-day') === target
                    );

                    if (exact) {
                        exact.scrollIntoView({
                            behavior: 'instant',
                            block: 'center',
                            inline: 'center'
                        });

                        exact.click();

                        return {
                            found: true,
                            type: 'data-sap-day',
                            value: exact.getAttribute('data-sap-day')
                        };
                    }

                    return {
                        found: false,
                        visibleDays: days.map(
                            el => el.getAttribute('data-sap-day') || ''
                        ).filter(Boolean)
                    };
                    """,
                    target_key,
                )

                if isinstance(result, dict) and result.get("found"):
                    print(
                        f"{label}: selected exact calendar date:",
                        target_ddmmyyyy,
                    )
                    time.sleep(0.5)

                    if self._verify_doc_upload_date_value(
                        icon_xpath,
                        target_date,
                    ):
                        self._close_doc_upload_date_picker(label)
                        return True

                # ---------------------------------------------------------
                # 2B. UI5 aria-label/title fallback
                # ---------------------------------------------------------
                fallback = self.driver.execute_script(
                    """
                    const target = arguments[0];

                    const visible = (el) => {
                        if (!el) return false;

                        const s = getComputedStyle(el);
                        const r = el.getBoundingClientRect();

                        return (
                            s.display !== 'none' &&
                            s.visibility !== 'hidden' &&
                            r.width > 0 &&
                            r.height > 0
                        );
                    };

                    const candidates = Array.from(
                        document.querySelectorAll(
                            '[aria-label], [title]'
                        )
                    ).filter(visible);

                    const formats = [
                        target,
                        target.slice(0,4) + '-' +
                            target.slice(4,6) + '-' +
                            target.slice(6,8),
                        target.slice(6,8) + '-' +
                            target.slice(4,6) + '-' +
                            target.slice(0,4)
                    ];

                    const found = candidates.find(el => {
                        const value = (
                            el.getAttribute('aria-label') ||
                            el.getAttribute('title') ||
                            ''
                        ).trim();

                        return formats.some(
                            f => value === f || value.includes(f)
                        );
                    });

                    if (!found) {
                        return false;
                    }

                    found.scrollIntoView({
                        behavior: 'instant',
                        block: 'center',
                        inline: 'center'
                    });

                    found.click();
                    return true;
                    """,
                    target_key,
                )

                if fallback:
                    print(
                        f"{label}: selected date using "
                        f"UI5 aria/title fallback:",
                        target_ddmmyyyy,
                    )
                    time.sleep(0.5)

                    if self._verify_doc_upload_date_value(
                        icon_xpath,
                        target_date,
                    ):
                        self._close_doc_upload_date_picker(label)
                        return True

                # ---------------------------------------------------------
                # 2C. Direct DatePicker input fallback
                #
                # For an icon such as:
                #     fromdate-icon
                #
                # UI5 normally has the associated input around:
                #     fromdate-inner
                #
                # We derive the base id instead of hard-coding a single
                # generated input id.
                # ---------------------------------------------------------
                input_result = self.driver.execute_script(
                    """
                    const iconXpath = arguments[0];
                    const values = arguments[1];

                    const visible = (el) => {
                        if (!el) return false;

                        const s = getComputedStyle(el);
                        const r = el.getBoundingClientRect();

                        return (
                            s.display !== 'none' &&
                            s.visibility !== 'hidden' &&
                            r.width > 0 &&
                            r.height > 0
                        );
                    };

                    const xpathResult = document.evaluate(
                        iconXpath,
                        document,
                        null,
                        XPathResult.FIRST_ORDERED_NODE_TYPE,
                        null
                    );

                    const icon = xpathResult.singleNodeValue;

                    if (!icon) {
                        return {
                            found: false,
                            reason: 'icon-not-found'
                        };
                    }

                    const iconId = icon.id || '';
                    const baseId = iconId.endsWith('-icon')
                        ? iconId.slice(0, -5)
                        : '';

                    let candidates = [];

                    if (baseId) {
                        candidates.push(
                            document.getElementById(baseId + '-inner')
                        );

                        candidates.push(
                            document.getElementById(baseId)
                        );

                        candidates.push(
                            document.querySelector(
                                '#' + CSS.escape(baseId) + ' input'
                            )
                        );
                    }

                    // Find the nearest visible input if the generated id
                    // is different from the expected UI5 convention.
                    let parent = icon.parentElement;

                    for (let i = 0; i < 5 && parent; i++) {
                        candidates.push(
                            ...parent.querySelectorAll('input')
                        );
                        parent = parent.parentElement;
                    }

                    const input = candidates.find(
                        el => el &&
                            el.tagName === 'INPUT' &&
                            visible(el)
                    );

                    if (!input) {
                        return {
                            found: false,
                            reason: 'date-input-not-found',
                            iconId: iconId
                        };
                    }

                    input.focus();
                    input.click();

                    const setter =
                        Object.getOwnPropertyDescriptor(
                            HTMLInputElement.prototype,
                            'value'
                        );

                    // Try the formats used by common SAP/UI5 locales.
                    for (const value of values) {
                        if (setter && setter.set) {
                            setter.set.call(input, value);
                        } else {
                            input.value = value;
                        }

                        input.dispatchEvent(
                            new Event('input', {
                                bubbles: true
                            })
                        );

                        input.dispatchEvent(
                            new Event('change', {
                                bubbles: true
                            })
                        );

                        input.dispatchEvent(
                            new Event('blur', {
                                bubbles: true
                            })
                        );

                        // Keep the last format in the field. The Python
                        // side verifies the actual displayed value.
                    }

                    return {
                        found: true,
                        inputId: input.id || '',
                        value: input.value || ''
                    };
                    """,
                    icon_xpath,
                    [
                        target_ddmmyyyy,
                        target_mmddyyyy,
                        target_ddmmyyyy_slash,
                        target_dot,
                        target_iso,
                    ],
                )

                if (
                    isinstance(input_result, dict)
                    and input_result.get("found")
                ):
                    print(
                        f"{label}: DatePicker input fallback used.",
                        "Input:",
                        input_result.get("inputId", ""),
                        "Value:",
                        input_result.get("value", ""),
                    )

                    # Press Enter so UI5 commits the DatePicker value.
                    try:
                        date_input_id = input_result.get("inputId", "")

                        if date_input_id:
                            input_element = self.driver.find_element(
                                By.ID,
                                date_input_id,
                            )
                        else:
                            input_element = None

                        if input_element is not None:
                            input_element.send_keys(
                                "\ue007"  # ENTER
                            )
                    except Exception:
                        pass

                    time.sleep(0.7)

                    if self._verify_doc_upload_date_value(
                        icon_xpath,
                        target_date,
                    ):
                        print(
                            f"{label}: verified date:",
                            target_ddmmyyyy,
                        )
                        self._close_doc_upload_date_picker(label)
                        return True

                # ---------------------------------------------------------
                # 2D. Month navigation fallback
                # ---------------------------------------------------------
                visible_days = []

                if isinstance(result, dict):
                    visible_days = [
                        str(x)
                        for x in result.get(
                            "visibleDays",
                            []
                        )
                        if x
                    ]

                if visible_days:
                    numeric_days = []

                    for value in visible_days:
                        if re.fullmatch(r"\d{8}", value):
                            try:
                                numeric_days.append(
                                    datetime.strptime(
                                        value,
                                        "%Y%m%d"
                                    ).date()
                                )
                            except ValueError:
                                pass

                    if numeric_days:
                        visible_min = min(numeric_days)
                        visible_max = max(numeric_days)

                        direction = None

                        if target_date < visible_min:
                            direction = "previous"
                        elif target_date > visible_max:
                            direction = "next"

                        if direction:
                            moved = self.driver.execute_script(
                                """
                                const direction = arguments[0];

                                const visible = (el) => {
                                    if (!el) return false;

                                    const s = getComputedStyle(el);
                                    const r = el.getBoundingClientRect();

                                    return (
                                        s.display !== 'none' &&
                                        s.visibility !== 'hidden' &&
                                        r.width > 0 &&
                                        r.height > 0
                                    );
                                };

                                const buttons = Array.from(
                                    document.querySelectorAll(
                                        'button, [role="button"], a'
                                    )
                                ).filter(visible);

                                const candidates = buttons.filter(el => {
                                    const text = (
                                        el.getAttribute('aria-label') ||
                                        el.getAttribute('title') ||
                                        el.textContent ||
                                        ''
                                    ).trim().toLowerCase();

                                    if (direction === 'previous') {
                                        return (
                                            text.includes('previous month') ||
                                            text === 'previous' ||
                                            text.includes('prev')
                                        );
                                    }

                                    return (
                                        text.includes('next month') ||
                                        text === 'next' ||
                                        text.includes('next')
                                    );
                                });

                                if (!candidates.length) {
                                    return false;
                                }

                                candidates[0].click();
                                return true;
                                """,
                                direction,
                            )

                            if moved:
                                time.sleep(0.5)
                                continue

            except (
                StaleElementReferenceException,
                NoSuchElementException,
            ):
                pass

            except WebDriverException as error:
                print(
                    f"{label}: date picker WebDriver warning:",
                    repr(error),
                )

            except Exception as error:
                print(
                    f"{label}: date picker selection warning:",
                    repr(error),
                )

            time.sleep(0.4)

        print(
            f"{label}: could not select date",
            target_ddmmyyyy,
            "within",
            timeout,
            "seconds.",
        )
        return False


    def _close_doc_upload_date_picker(self, label="DatePicker"):
        """Close the SAP UI5 DatePicker popup before the next control is clicked."""
        if self.driver is None:
            return False

        try:
            body = self.driver.find_element(By.TAG_NAME, "body")
            body.send_keys(Keys.ESCAPE)
            time.sleep(0.5)
        except Exception as error:
            print(f"{label}: Escape warning:", repr(error))

        # Check whether a visible calendar is still present.
        try:
            still_open = self.driver.execute_script("""
                const visible = (el) => {
                    if (!el) return false;
                    const s = getComputedStyle(el);
                    const r = el.getBoundingClientRect();
                    return s.display !== 'none' &&
                           s.visibility !== 'hidden' &&
                           r.width > 0 &&
                           r.height > 0;
                };

                return Array.from(
                    document.querySelectorAll(
                        '.sapUiCal, .sapUiDtPicker, [role="grid"]'
                    )
                ).some(visible);
            """)

            if not still_open:
                print(f"{label}: DatePicker popup closed.")
                return True

        except Exception as error:
            print(f"{label}: popup check warning:", repr(error))

        # Fallback: send Escape to visible UI5 inputs.
        try:
            for element in self.driver.find_elements(
                By.CSS_SELECTOR,
                "input.sapMInputBaseInner"
            ):
                try:
                    if element.is_displayed():
                        element.send_keys(Keys.ESCAPE)
                        time.sleep(0.4)
                        break
                except Exception:
                    continue
        except Exception as error:
            print(f"{label}: input Escape warning:", repr(error))

        try:
            still_open = self.driver.execute_script("""
                const visible = (el) => {
                    if (!el) return false;
                    const s = getComputedStyle(el);
                    const r = el.getBoundingClientRect();
                    return s.display !== 'none' &&
                           s.visibility !== 'hidden' &&
                           r.width > 0 &&
                           r.height > 0;
                };

                return Array.from(
                    document.querySelectorAll(
                        '.sapUiCal, .sapUiDtPicker, [role="grid"]'
                    )
                ).some(visible);
            """)

            if still_open:
                print(f"{label}: WARNING - DatePicker popup is still visible.")
                return False

            print(f"{label}: DatePicker popup closed successfully.")
            return True

        except Exception as error:
            print(f"{label}: final popup check warning:", repr(error))
            return False

    def _verify_doc_upload_date_value(
        self,
        icon_xpath,
        target_date,
    ):
        """
        Verify that the DatePicker input associated with the supplied icon
        contains the requested date.

        We accept the common SAP/UI5 date display formats so this verification
        is not tied to one browser/locale setting.
        """
        if self.driver is None:
            return False

        target_values = {
            target_date.strftime("%d-%m-%Y"),
            target_date.strftime("%m/%d/%Y"),
            target_date.strftime("%d/%m/%Y"),
            target_date.strftime("%d.%m.%Y"),
            target_date.strftime("%Y-%m-%d"),
            target_date.strftime("%d %b %Y"),
            target_date.strftime("%b %d, %Y"),
        }

        try:
            result = self.driver.execute_script(
                """
                const iconXpath = arguments[0];

                const visible = (el) => {
                    if (!el) return false;

                    const s = getComputedStyle(el);
                    const r = el.getBoundingClientRect();

                    return (
                        s.display !== 'none' &&
                        s.visibility !== 'hidden' &&
                        r.width > 0 &&
                        r.height > 0
                    );
                };

                const xpathResult = document.evaluate(
                    iconXpath,
                    document,
                    null,
                    XPathResult.FIRST_ORDERED_NODE_TYPE,
                    null
                );

                const icon = xpathResult.singleNodeValue;

                if (!icon) {
                    return [];
                }

                const iconId = icon.id || '';
                const baseId = iconId.endsWith('-icon')
                    ? iconId.slice(0, -5)
                    : '';

                let candidates = [];

                if (baseId) {
                    candidates.push(
                        document.getElementById(baseId + '-inner')
                    );

                    candidates.push(
                        document.getElementById(baseId)
                    );

                    candidates.push(
                        document.querySelector(
                            '#' + CSS.escape(baseId) + ' input'
                        )
                    );
                }

                let parent = icon.parentElement;

                for (let i = 0; i < 5 && parent; i++) {
                    candidates.push(
                        ...parent.querySelectorAll('input')
                    );
                    parent = parent.parentElement;
                }

                return candidates
                    .filter(
                        el =>
                            el &&
                            el.tagName === 'INPUT' &&
                            visible(el)
                    )
                    .map(
                        el =>
                            (el.value || '').trim()
                    )
                    .filter(Boolean);
                """,
                icon_xpath,
            )

            if not result:
                return False

            normalized_targets = {
                str(value).strip().lower()
                for value in target_values
            }

            actual_values = {
                str(value).strip().lower()
                for value in result
            }

            matched = bool(
                normalized_targets.intersection(actual_values)
            )

            if matched:
                print(
                    "Date verification passed:",
                    target_date.strftime("%d-%m-%Y"),
                )
            else:
                print(
                    "Date verification failed.",
                    "Expected:",
                    sorted(normalized_targets),
                    "Actual:",
                    sorted(actual_values),
                )

            return matched

        except Exception as error:
            print(
                "Date verification warning:",
                repr(error),
            )
            return False

    # ------------------------------------------------------------------------
    # OTP MAIL SETTINGS - LOAD DYNAMICALLY FROM DATABASE
    # ------------------------------------------------------------------------

    def _get_otp_mail_settings(self):
        """
        Load OTP mail configuration directly from dbo.MailSettings.

        NO .env file.
        NO config.py OTP constants.
        NO hardcoded mailbox credentials.

        The newest active MailSettings row is used.

        Returns:
            {
                "server": str,
                "port": int,
                "imap_port": int,
                "username": str,
                "password": str,
                "subject": str,
                "sender": str,
            }

            or None when configuration is missing/invalid.
        """

        connection = None
        cursor = None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT TOP 1
                    Id,
                    MailServer,
                    MailPort,
                    EmailId,
                    EmailPassword,
                    OtpSubject,
                    OtpSender
                FROM dbo.MailSettings
                WHERE ISNULL(IsActive, 0) = 1
                ORDER BY Id DESC
                """
            )

            row = cursor.fetchone()

            if not row:
                print(
                    "OTP MAIL CONFIG ERROR: "
                    "No active row found in dbo.MailSettings."
                )
                return None

            settings_id = row[0]
            server = str(row[1] or "").strip()
            username = str(row[3] or "").strip()
            password = str(row[4] or "")
            subject = str(row[5] or "").strip()
            sender = str(row[6] or "").strip()

            try:
                configured_port = int(row[2])
            except (TypeError, ValueError):
                print(
                    "OTP MAIL CONFIG ERROR: "
                    f"Invalid MailPort in dbo.MailSettings. "
                    f"Row Id={settings_id}, Value={row[2]!r}"
                )
                return None

            if not server:
                print(
                    "OTP MAIL CONFIG ERROR: "
                    f"MailServer is empty. Row Id={settings_id}"
                )
                return None

            if not username:
                print(
                    "OTP MAIL CONFIG ERROR: "
                    f"EmailId is empty. Row Id={settings_id}"
                )
                return None

            if not password:
                print(
                    "OTP MAIL CONFIG ERROR: "
                    f"EmailPassword is empty. Row Id={settings_id}"
                )
                return None

            if not subject:
                print(
                    "OTP MAIL CONFIG ERROR: "
                    f"OtpSubject is empty. Row Id={settings_id}"
                )
                return None

            if not sender:
                print(
                    "OTP MAIL CONFIG ERROR: "
                    f"OtpSender is empty. Row Id={settings_id}"
                )
                return None

            if configured_port < 1 or configured_port > 65535:
                print(
                    "OTP MAIL CONFIG ERROR: "
                    f"MailPort must be between 1 and 65535. "
                    f"Row Id={settings_id}, Port={configured_port}"
                )
                return None

            # This application reads mail using IMAP4_SSL.
            # 995 is POP3 SSL, therefore translate only the connection
            # port to IMAP 993. The database value is NOT modified.
            imap_port = (
                993
                if configured_port == 995
                else configured_port
            )

            if configured_port == 995:
                print(
                    "MailSettings MailPort is 995 (POP3 SSL). "
                    "Using IMAP SSL port 993 for OTP reading."
                )

            print("=" * 70)
            print("OTP MAIL SETTINGS LOADED FROM dbo.MailSettings")
            print("MailSettings Id :", settings_id)
            print("IMAP Server     :", server)
            print("Configured Port :", configured_port)
            print("IMAP Port       :", imap_port)
            print("Email ID        :", username)
            print("OTP Subject     :", subject)
            print("OTP Sender      :", sender)
            print("=" * 70)

            return {
                "id": settings_id,
                "server": server,
                "port": configured_port,
                "imap_port": imap_port,
                "username": username,
                "password": password,
                "subject": subject,
                "sender": sender,
            }

        except Exception as error:
            print("=" * 70)
            print("OTP MAIL SETTINGS DATABASE ERROR")
            print(type(error).__name__, repr(error))
            print("=" * 70)
            return None

        finally:
            try:
                if cursor is not None:
                    cursor.close()
            except Exception:
                pass

            try:
                if connection is not None:
                    connection.close()
            except Exception:
                pass

    # ------------------------------------------------------------------------
    # MAILBOX - CURRENT UIDS
    # ------------------------------------------------------------------------

    def _get_mail_uids(self):
        """
        Get current INBOX UIDs before requesting a new OTP.

        Mail configuration is loaded fresh from dbo.MailSettings
        every time this method is called.
        """

        settings = self._get_otp_mail_settings()

        if not settings:
            return set()

        mail = None

        try:
            print("=" * 70)
            print("CONNECTING TO OTP MAILBOX")
            print("Source        : dbo.MailSettings")
            print("IMAP Server   :", settings["server"])
            print("DB MailPort   :", settings["port"])
            print("IMAP Port     :", settings["imap_port"])
            print("Username      :", settings["username"])
            print("=" * 70)

            mail = imaplib.IMAP4_SSL(
                settings["server"],
                settings["imap_port"],
                timeout=20,
            )

            print("IMAP SSL connection successful.")

            status, response = mail.login(
                settings["username"],
                settings["password"],
            )

            print("IMAP login status:", status)

            if status != "OK":
                print("IMAP LOGIN FAILED:", response)
                return set()

            status, _ = mail.select("INBOX")

            print("INBOX select status:", status)

            if status != "OK":
                print("Could not select INBOX.")
                return set()

            status, data = mail.uid(
                "search",
                None,
                "ALL",
            )

            if (
                status != "OK"
                or not data
                or not data[0]
            ):
                print("No messages found in INBOX.")
                return set()

            uids = set(data[0].split())

            print(
                "Existing mailbox message count:",
                len(uids),
            )

            return uids

        except Exception as error:
            print("=" * 70)
            print("OTP MAILBOX CONNECTION ERROR")
            print(type(error).__name__, repr(error))
            print("=" * 70)
            return set()

        finally:
            try:
                if mail is not None:
                    mail.logout()
            except Exception:
                pass

    # ------------------------------------------------------------------------
    # MAILBOX - WAIT FOR OTP
    # ------------------------------------------------------------------------

    def _wait_for_new_otp_email(
        self,
        baseline_uids,
        timeout=110,
        poll_seconds=3,
    ):
        """Wait for the latest Mahindra OTP email."""
        print("=" * 70)
        print("WAITING FOR MAHINDRA OTP EMAIL")
        print("Timeout:", timeout, "seconds")
        print("=" * 70)

        started = time.time()

        while time.time() - started < timeout:
            if self._stop_event.is_set():
                return None

            otp = self._read_newest_otp_from_mailbox(baseline_uids)

            if otp:
                print("=" * 70)
                print("OTP FOUND:", otp)
                print("=" * 70)
                return otp

            print(f"OTP not found yet. Retrying in {poll_seconds} seconds...")
            time.sleep(poll_seconds)

        print("=" * 70)
        print("OTP WAIT TIMEOUT")
        print("=" * 70)
        return None

    # ------------------------------------------------------------------------
    # READ LATEST MAHINDRA OTP
    # ------------------------------------------------------------------------

    def _read_newest_otp_from_mailbox(self, baseline_uids):
        """
        Read the newest OTP email matching OtpSender and OtpSubject
        from the active dbo.MailSettings row.

        The OTP value itself is extracted as a six-digit number from
        the email body.
        """

        settings = self._get_otp_mail_settings()

        if not settings:
            print(
                "OTP reader stopped because dbo.MailSettings "
                "configuration is missing."
            )
            return None

        mail = None

        try:
            print("Connecting to IMAP for OTP check...")
            print(
                "Using dbo.MailSettings Id:",
                settings["id"],
            )

            mail = imaplib.IMAP4_SSL(
                settings["server"],
                settings["imap_port"],
                timeout=20,
            )

            print("IMAP connection OK.")

            status, response = mail.login(
                settings["username"],
                settings["password"],
            )

            print("IMAP login:", status)

            if status != "OK":
                print("IMAP login failed:", response)
                return None

            status, _ = mail.select("INBOX")
            print("INBOX:", status)

            if status != "OK":
                print("Unable to open INBOX.")
                return None

            status, data = mail.uid("search", None, "ALL")

            if status != "OK" or not data or not data[0]:
                print("No emails found.")
                return None

            current_uids = data[0].split()
            print("Mailbox contains", len(current_uids), "messages.")

            # Newest first. Check enough recent mail to handle delivery delays.
            ordered_uids = list(reversed(current_uids[-30:]))

            login_time = (
                self.otp_wait_started
                or datetime.now(timezone.utc)
            )
            freshness_time = login_time - timedelta(seconds=30)

            for uid in ordered_uids:
                try:
                    status, msg_data = mail.uid(
                        "fetch",
                        uid,
                        "(RFC822)",
                    )

                    if status != "OK" or not msg_data:
                        continue

                    raw_email = None

                    for part in msg_data:
                        if (
                            isinstance(part, tuple)
                            and len(part) > 1
                            and isinstance(part[1], bytes)
                        ):
                            raw_email = part[1]
                            break

                    if not raw_email:
                        continue

                    msg = email.message_from_bytes(raw_email)

                    subject = self._decode_email_header(
                        msg.get("Subject", "")
                    ).strip()

                    sender = self._decode_email_header(
                        msg.get("From", "")
                    ).strip()

                    email_date = msg.get("Date", "")
                    body = self._get_email_body(msg)
                    body_text = self._normalise_email_text(body)

                    print(
                        f"Checking UID {uid.decode(errors='ignore')} | "
                        f"From: {sender} | "
                        f"Subject: {subject} | "
                        f"Date: {email_date}"
                    )

                    # Accept a new UID. If the UID was already present before
                    # the login, only accept it when the email is very recent.
                    is_fresh = uid not in baseline_uids

                    if not is_fresh:
                        try:
                            parsed_date = parsedate_to_datetime(email_date)

                            if parsed_date.tzinfo is None:
                                parsed_date = parsed_date.replace(
                                    tzinfo=timezone.utc
                                )
                            else:
                                parsed_date = parsed_date.astimezone(
                                    timezone.utc
                                )

                            is_fresh = parsed_date >= freshness_time

                        except Exception as date_error:
                            print(
                                "OTP date parse warning:",
                                repr(date_error),
                            )

                    if not is_fresh:
                        continue

                    sender_lower = sender.lower()
                    subject_lower = subject.lower()
                    body_lower = body_text.lower()

                    configured_sender = (
                        settings["sender"]
                        .strip()
                        .lower()
                    )

                    configured_subject = (
                        settings["subject"]
                        .strip()
                        .lower()
                    )

                    # OtpSender is read from dbo.MailSettings.
                    # Email "From" can contain a display name, so
                    # use substring matching instead of exact equality.
                    sender_matches = (
                        configured_sender in sender_lower
                    )

                    # OtpSubject is read from dbo.MailSettings.
                    # The mailbox subject may contain a prefix/suffix,
                    # therefore use case-insensitive substring matching.
                    subject_matches = (
                        configured_subject in subject_lower
                    )

                    body_matches = (
                        "otp" in body_lower
                        or "one time password" in body_lower
                        or "verification code" in body_lower
                    )

                    if not sender_matches:
                        continue

                    if not subject_matches:
                        continue

                    if not body_matches:
                        continue

                    print("Mahindra OTP email found.")
                    print("Email body:", repr(body_text[:1500]))

                    # Exact pattern for the email in the screenshot:
                    # "OTP for this login is: 891705"
                    otp_patterns = [
                        r"\bOTP\s+for\s+(?:this\s+)?(?:login|logon)\s+is\s*:\s*(\d{6})\b",
                        r"\bOTP\s*(?:is|:|-)\s*(\d{6})\b",
                        r"\blogin\s+is\s*:\s*(\d{6})\b",
                        r"\blogon\s+is\s*:\s*(\d{6})\b",
                        r"\b(?:OTP|code)\s*:\s*(\d{6})\b",
                        r"(?<!\d)(\d{6})(?!\d)",
                    ]

                    for pattern in otp_patterns:
                        match = re.search(
                            pattern,
                            body_text,
                            re.IGNORECASE,
                        )

                        if match:
                            otp = match.group(1)

                            print("=" * 70)
                            print("MAHINDRA OTP EXTRACTED:", otp)
                            print("=" * 70)

                            return otp

                except Exception as message_error:
                    print(
                        "OTP message read error:",
                        repr(message_error),
                    )
                    continue

            print(
                "No matching fresh Mahindra OTP email found "
                "in the latest 30 messages."
            )
            return None

        except Exception as error:
            print("=" * 70)
            print("OTP MAIL READ ERROR")
            print(type(error).__name__, repr(error))

            if "POP3 ready" in str(error):
                print(
                    "PROTOCOL ERROR: mail server returned a POP3 greeting. "
                    "IMAP must use port 993, not 995."
                )

            print("=" * 70)
            return None

        finally:
            try:
                if mail is not None:
                    mail.logout()
            except Exception:
                pass

    # ------------------------------------------------------------------------
    # EMAIL HELPERS
    # ------------------------------------------------------------------------

    @staticmethod
    def _decode_email_header(value):
        """Safely decode a MIME email header."""

        if not value:
            return ""

        try:
            parts = decode_header(str(value))
            decoded = []

            for part, encoding in parts:
                if isinstance(part, bytes):
                    try:
                        decoded.append(
                            part.decode(
                                encoding or "utf-8",
                                errors="replace",
                            )
                        )
                    except Exception:
                        decoded.append(
                            part.decode(
                                "utf-8",
                                errors="replace",
                            )
                        )
                else:
                    decoded.append(str(part))

            return "".join(decoded)

        except Exception:
            return str(value)

    @staticmethod
    def _get_email_body(message):
        """Return the email plain-text body."""

        try:
            if message.is_multipart():
                plain_parts = []
                html_parts = []

                for part in message.walk():
                    content_type = part.get_content_type()

                    disposition = str(
                        part.get("Content-Disposition", "")
                    ).lower()

                    if "attachment" in disposition:
                        continue

                    payload = part.get_payload(decode=True)

                    if not payload:
                        continue

                    charset = (
                        part.get_content_charset()
                        or "utf-8"
                    )

                    decoded = payload.decode(
                        charset,
                        errors="replace",
                    )

                    if content_type == "text/plain":
                        plain_parts.append(decoded)

                    elif content_type == "text/html":
                        html_parts.append(decoded)

                if plain_parts:
                    return "\n".join(plain_parts)

                if html_parts:
                    return "\n".join(html_parts)

                return ""

            payload = message.get_payload(decode=True)

            if payload is None:
                value = message.get_payload()
                return value if isinstance(value, str) else ""

            charset = (
                message.get_content_charset()
                or "utf-8"
            )

            return payload.decode(
                charset,
                errors="replace",
            )

        except Exception as error:
            print("Email body decode error:", repr(error))
            return ""

    @staticmethod
    def _normalise_email_text(text):
        """Convert HTML/email whitespace to searchable text."""

        if not text:
            return ""

        text = re.sub(
            r"<br\s*/?>",
            "\n",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"</p\s*>",
            "\n",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(r"<[^>]+>", " ", text)

        text = re.sub(
            r"&nbsp;",
            " ",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"&amp;",
            "&",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(r"\s+", " ", text)

        return text.strip()

    # ------------------------------------------------------------------------
    # CLEANUP
    # ------------------------------------------------------------------------

    def _handle_back_clicked(self):
        """Compatibility method for existing DashboardPage code."""

        self.cleanup()

        if callable(self.on_back):
            self.on_back()

    def cleanup(self):
        """
        Stop automation and close the external Edge browser.
        """

        print("Cleaning up Mahindra automation...")

        self._stop_event.set()
        self._stop_windows_security_watcher()
        self._running = False

        try:
            if self.driver is not None:
                try:
                    self.driver.switch_to.default_content()
                except Exception:
                    pass

                self.driver.quit()
        except Exception as error:
            print("Edge quit error:", repr(error))

        self.driver = None
        self._winsec_watcher_active = False

        self.current_asn_file_path = None
        self.self_service_window_handle = None

        self.otp_started = False
        self.otp_verify_clicked = False
        self.otp_value = None
        self.otp_wait_started = None
        self.otp_baseline_uids = set()

        print("Mahindra automation cleaned up.")
