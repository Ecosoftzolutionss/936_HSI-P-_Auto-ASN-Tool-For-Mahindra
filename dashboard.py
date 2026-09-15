from pathlib import Path
import imaplib
import email
import re
import threading
import time
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta

from PyQt6.QtCore import Qt, QByteArray, QUrl, QTimer
from PyQt6.QtGui import QPixmap, QFont, QIcon, QImage, QPainter
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,)
from PyQt6.QtWebEngineWidgets import QWebEngineView
# NOTE: in PyQt6, QWebEnginePage / QWebEngineProfile / QWebEngineScript live
# in QtWebEngineCore, not QtWebEngineWidgets (only QWebEngineView stays there).
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineScript
from PyQt6.QtSvg import QSvgRenderer

from user_master import UserMasterPage
from settings import SettingsPage

# =================================================================
# APPLICATION CONFIGURATION
# =================================================================
# OTP/mail credentials are loaded from environment variables via
# config.py. Do not store real credentials in this source file.
from config import (
    OTP_MAIL_SERVER,
    OTP_MAIL_PORT,
    OTP_MAIL_USERNAME,
    OTP_MAIL_PASSWORD,
    OTP_SENDER,
    OTP_SUBJECT,
)

# =================================================================
# JS COMPATIBILITY POLYFILLS
# =================================================================
#
# Kept for safety/back-compat even though PyQt6's bundled QtWebEngine
# uses a modern Chromium that already supports Array.prototype.at()
# and the JS syntax (logical assignment operators, etc.) that broke
# the old PyQt5 build. This no-ops on modern engines but costs nothing
# to leave in, and protects against any future site code that assumes
# even newer JS features than the engine on hand supports.

_JS_COMPAT_POLYFILLS_INSTALLED = False


def _install_js_compat_polyfills():
    """
    Install the Array/String.prototype.at() polyfill on the default
    QWebEngineProfile. Safe to call multiple times - only installs once.
    Must be called before any QWebEngineView/QWebEnginePage is created,
    otherwise pages created earlier won't have the fix applied.
    """

    global _JS_COMPAT_POLYFILLS_INSTALLED

    if _JS_COMPAT_POLYFILLS_INSTALLED:
        return

    polyfill_js = """
    (function () {
        function at(n) {
            n = Math.trunc(n) || 0;
            if (n < 0) n += this.length;
            if (n < 0 || n >= this.length) return undefined;
            return this[n];
        }

        var targets = [Array, String];

        try {
            targets.push(Object.getPrototypeOf(Int8Array));
        } catch (e) {
            // Typed arrays not available - ignore.
        }

        targets.forEach(function (C) {
            if (C && C.prototype && !C.prototype.at) {
                Object.defineProperty(C.prototype, 'at', {
                    value: at,
                    writable: true,
                    enumerable: false,
                    configurable: true,
                });
            }
        });
    })();
    """

    script = QWebEngineScript()
    script.setName("es2022_at_polyfill")
    script.setSourceCode(polyfill_js)
    # Run before the page's own scripts, on every frame (Mahindra's
    # portal may load parts of itself inside iframes).
    script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    script.setRunsOnSubFrames(True)

    QWebEngineProfile.defaultProfile().scripts().insert(script)

    _JS_COMPAT_POLYFILLS_INSTALLED = True


class EmbeddedBrowserPage(QWebEnginePage):
    """
    WebEngine page used for the Mahindra Supplier Portal.

    Mahindra may use JavaScript/SSO redirects and target=_blank links.
    Keep those navigations inside the HSI embedded browser.
    """

    def createWindow(self, window_type):
        # Returning this page keeps target=_blank / popup navigation
        # inside the same embedded browser instead of opening Chrome/Edge.
        return self

    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        print(
            f"[Mahindra JS] {source_id}:{line_number} - {message}"
        )
        super().javaScriptConsoleMessage(
            level, message, line_number, source_id
        )


class DashboardPage(QWidget):

    # =========================================================
    # COLORS
    # =========================================================

    BG_COLOR = "#EEF1FA"
    WHITE = "#FFFFFF"
    PRIMARY = "#1457E6"
    TEXT_DARK = "#10182D"
    TEXT_GREY = "#71809E"
    CARD_COLOR = "#E4E9F7"
    ICON_BG = "#F4F7FF"

    # =========================================================
    # INITIALIZATION
    # =========================================================

    def __init__(self, master=None, user=None, logout_callback=None):
        super().__init__(master)

        # Must happen before any QWebEngineView/QWebEnginePage is
        # created (including the preloaded Mahindra browser below),
        # otherwise the polyfill script won't be present when those
        # pages first load. See _install_js_compat_polyfills() above.
        _install_js_compat_polyfills()

        self.user = user
        self.logout_callback = logout_callback

        self.base_path = Path(__file__).resolve().parent
        self.user_master_page = None
        self.mail_master_page = None
        self.settings_page = None
        self.automation_page = None
        self.supplier_browser = None
        self.web_profile = None
        self.web_page = None
        self.preload_browser = None
        self.preload_page = None
        self.preload_ready = False

        # OTP automation state
        self.otp_wait_started = None
        self.otp_value = None
        self.otp_timer = None
        self.otp_fetch_in_progress = False
        self.otp_fetch_worker_running = False
        self.otp_worker_result = None
        self.otp_fetch_attempts = 0
        self.otp_fetch_started_at = 0

        # Mahindra login / OTP state
        self.otp_started = False
        self.otp_fill_attempts = 0
        self.otp_verify_clicked = False

        self.setStyleSheet(
            f"""
            QWidget {{
                font-family: "Segoe UI";
                color: {self.TEXT_DARK};
            }}
            """
        )

        self.create_ui()

        # Mahindra WebEngine is started only when Automation is clicked.
        # This keeps User Master/Mail Master/Settings navigation stable.

    # =========================================================
    # ICON
    # =========================================================

    def create_icon(self, name, size=22, color="#1457E6"):
        """
        PyQt6 replacement for ctkfontawesome.

        Unicode symbols are used so this file has no dependency on
        CustomTkinter or ctkfontawesome.
        """
        icons = {
            "user": "●",
            "users": "👥",
            "mail": "✉",
            "cog": "⚙",
            "sign-out-alt": "↪",
            "arrow-right": "→",
            "automation": "⚙",
        }

        label = QLabel(icons.get(name, "•"))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            f"""
            QLabel {{
                color: {color};
                background: transparent;
                border: none;
                font-family: "Segoe UI Symbol";
                font-size: {size}px;
            }}
            """
        )

        return label

    # =========================================================
    # CREATE UI
    # =========================================================

    def create_ui(self):

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # =====================================================
        # HEADER
        # =====================================================

        self.header = QFrame()
        self.header.setFixedHeight(70)
        self.header.setStyleSheet(
            """
            QFrame {
                background: #FFFFFF;
                border: none;
            }
            """
        )

        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        header_layout.setSpacing(0)

        # =====================================================
        # LOGO
        # =====================================================

        self.logo_label = QLabel()
        self.logo_label.setFixedSize(145, 48)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo_paths = [
            self.base_path / "assets" / "HSI_LOGO.png",
            self.base_path / "assets" / "HSI.png",
            self.base_path / "assets" / "Dashtoplogo.png",
        ]

        logo_path = None

        for path in logo_paths:
            if path.exists():
                logo_path = path
                break

        if logo_path:

            logo_pixmap = QPixmap(str(logo_path))

            if not logo_pixmap.isNull():

                self.logo_label.setPixmap(
                    logo_pixmap.scaled(
                        145,
                        48,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

            else:
                self.set_logo_fallback()

        else:
            self.set_logo_fallback()

        header_layout.addWidget(self.logo_label)

        header_layout.addStretch()

        # =====================================================
        # USER AREA
        # =====================================================

        # Compact user profile area matching the reference header:
        # circular icon -> username/role stacked -> dropdown arrow -> logout.
        self.user_area = QFrame()
        self.user_area.setFixedHeight(40)
        self.user_area.setStyleSheet("""
            QFrame {
                background: transparent;
                border: none;
            }
        """)

        user_layout = QHBoxLayout(self.user_area)
        user_layout.setContentsMargins(0, 0, 0, 0)
        user_layout.setSpacing(0)

        # User icon circle
        self.user_icon_frame = QFrame()
        self.user_icon_frame.setFixedSize(32, 32)
        self.user_icon_frame.setStyleSheet("""
            QFrame {
                background: #EEF4FF;
                border: none;
                border-radius: 16px;
            }
        """)

        icon_layout = QVBoxLayout(self.user_icon_frame)
        icon_layout.setContentsMargins(0, 0, 0, 0)

        # Person icon matching the reference image.
        user_svg = """
        <svg width="32" height="32" viewBox="0 0 32 32"
             xmlns="http://www.w3.org/2000/svg">
            <circle cx="16" cy="16" r="16" fill="#EEF4FF"/>
            <circle cx="16" cy="11.5" r="4" fill="#2E6DEB"/>
            <path d="M9.5 24c0-4.1 2.9-7 6.5-7s6.5 2.9 6.5 7"
                  fill="#2E6DEB"/>
        </svg>
        """

        self.user_icon_label = QLabel()
        self.user_icon_label.setFixedSize(32, 32)

        user_image = QImage(32, 32, QImage.Format.Format_ARGB32)
        user_image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(user_image)
        renderer = QSvgRenderer(QByteArray(user_svg.encode("utf-8")))
        renderer.render(painter)
        painter.end()

        self.user_icon_label.setPixmap(QPixmap.fromImage(user_image))
        icon_layout.addWidget(self.user_icon_label)

        user_layout.addWidget(self.user_icon_frame)
        user_layout.addSpacing(8)

        # Username + role stacked vertically
        user_text_frame = QFrame()
        user_text_frame.setFixedWidth(82)
        user_text_frame.setStyleSheet("""
            QFrame {
                background: transparent;
                border: none;
            }
        """)

        user_text_layout = QVBoxLayout(user_text_frame)
        user_text_layout.setContentsMargins(0, 0, 0, 0)
        user_text_layout.setSpacing(1)
        user_text_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        username = self.get_username()
        role = self.get_role()

        self.user_name_label = QLabel(username)
        self.user_name_label.setStyleSheet(f"""
            QLabel {{
                color: {self.TEXT_DARK};
                background: transparent;
                border: none;
                font-size: 10px;
                font-weight: bold;
            }}
        """)
        self.user_name_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        self.role_label = QLabel(role)
        self.role_label.setStyleSheet(f"""
            QLabel {{
                color: {self.TEXT_GREY};
                background: transparent;
                border: none;
                font-size: 7px;
            }}
        """)
        self.role_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        user_text_layout.addWidget(self.user_name_label)
        user_text_layout.addWidget(self.role_label)

        user_layout.addWidget(user_text_frame)

        # Small dropdown arrow
        self.profile_arrow = QLabel("⌄")
        self.profile_arrow.setFixedSize(16, 30)
        self.profile_arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.profile_arrow.setStyleSheet("""
            QLabel {
                color: #64748B;
                background: transparent;
                border: none;
                font-size: 13px;
            }
        """)
        user_layout.addWidget(self.profile_arrow)
        user_layout.addSpacing(7)

        # Logout button
        self.logout_button = QPushButton()
        self.logout_button.setFixedSize(32, 32)
        self.logout_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.logout_button.setToolTip("Logout")

        logout_svg = """
        <svg width="32" height="32" viewBox="0 0 32 32"
             xmlns="http://www.w3.org/2000/svg">
            <rect x="0" y="0" width="32" height="32" rx="7" fill="#2E6DEB"/>
            <path d="M10 7.5h7.2c.8 0 1.3.5 1.3 1.3v3"
                  fill="none" stroke="white" stroke-width="1.8"
                  stroke-linecap="round"/>
            <path d="M18.5 20.2v2.9c0 .8-.5 1.4-1.3 1.4H10"
                  fill="none" stroke="white" stroke-width="1.8"
                  stroke-linecap="round"/>
            <path d="M10 7.5v17"
                  fill="none" stroke="white" stroke-width="1.8"
                  stroke-linecap="round"/>
            <path d="M13.2 16h9.2"
                  fill="none" stroke="white" stroke-width="1.9"
                  stroke-linecap="round"/>
            <path d="M19 12.8L22.5 16 19 19.2"
                  fill="none" stroke="white" stroke-width="1.9"
                  stroke-linecap="round"
                  stroke-linejoin="round"/>
        </svg>
        """

        logout_image = QImage(32, 32, QImage.Format.Format_ARGB32)
        logout_image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(logout_image)
        renderer = QSvgRenderer(QByteArray(logout_svg.encode("utf-8")))
        renderer.render(painter)
        painter.end()

        self.logout_button.setIcon(QIcon(QPixmap.fromImage(logout_image)))
        self.logout_button.setIconSize(self.logout_button.size())
        self.logout_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                padding: 0px;
            }
            QPushButton:hover {
                background: transparent;
            }
            QPushButton:pressed {
                background: transparent;
            }
        """)

        self.logout_button.clicked.connect(self.logout)
        user_layout.addWidget(self.logout_button)

        header_layout.addWidget(self.user_area)

        root.addWidget(
            self.header
        )

        # =====================================================
        # CONTENT
        # =====================================================

        self.content = QFrame()
        self.content.setStyleSheet(
            f"""
            QFrame {{
                background: {self.BG_COLOR};
                border: none;
            }}
            """
        )

        content_layout = QVBoxLayout(
            self.content
        )

        content_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        content_layout.setSpacing(0)

        # =====================================================
        # WELCOME AREA
        # =====================================================

        welcome_container = QFrame()
        welcome_container.setStyleSheet(
            """
            QFrame {
                background: transparent;
                border: none;
            }
            """
        )

        welcome_layout = QVBoxLayout(
            welcome_container
        )

        welcome_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        welcome_layout.setSpacing(0)

        # The original used relx=0.035/rely positions.
        # Margins below retain the same visual spacing.

        welcome_layout.setContentsMargins(
            35,
            35,
            35,
            0,
        )

        # =====================================================
        # WELCOME
        # =====================================================

        self.welcome_label = QLabel(
            f"Welcome {self.get_username()}!"
        )

        self.welcome_label.setStyleSheet(
            f"""
            QLabel {{
                color: {self.TEXT_DARK};
                background: transparent;
                border: none;
                font-size: 28px;
                font-weight: bold;
            }}
            """
        )

        welcome_layout.addWidget(
            self.welcome_label
        )

        # =====================================================
        # DESCRIPTION
        # =====================================================

        self.description_label = QLabel(
            "Select an option below to manage the system."
        )

        self.description_label.setStyleSheet(
            f"""
            QLabel {{
                color: {self.TEXT_GREY};
                background: transparent;
                border: none;
                font-size: 12px;
            }}
            """
        )

        welcome_layout.addSpacing(5)

        welcome_layout.addWidget(
            self.description_label
        )

        # =====================================================
        # BLUE LINE
        # =====================================================

        self.blue_line = QFrame()
        self.blue_line.setFixedSize(
            45,
            3,
        )

        self.blue_line.setStyleSheet(
            f"""
            QFrame {{
                background: {self.PRIMARY};
                border: none;
                border-radius: 2px;
            }}
            """
        )

        welcome_layout.addSpacing(15)

        welcome_layout.addWidget(
            self.blue_line
        )

        content_layout.addWidget(
            welcome_container
        )

        # =====================================================
        # CARDS AREA
        # =====================================================

        cards_container = QFrame()
        cards_container.setStyleSheet(
            """
            QFrame {
                background: transparent;
                border: none;
            }
            """
        )

        cards_layout = QHBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 25, 0, 0)
        cards_layout.setSpacing(20)

        # Keep all four cards centered.
        cards_layout.addStretch(1)

        # =====================================================
        # USER MASTER CARD
        # =====================================================

        self.user_card = self.create_card(
            title="User Master",
            description=(
                "Manage users, roles and permissions\n"
                "for the HSI Automation Portal."
            ),
            icon="users",
            command=self.open_user_master,
        )

        cards_layout.addWidget(
            self.user_card,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        # =====================================================
        # MAIL MASTER CARD
        # =====================================================

        self.mail_master_card = self.create_card(
            title="Mail Master",
            description=(
                "Configure mail server and\n"
                "OTP email settings."
            ),
            icon="mail",
            command=self.open_mail_master,
        )

        cards_layout.addWidget(
            self.mail_master_card,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        # =====================================================
        # SETTINGS CARD
        # =====================================================

        self.settings_card = self.create_card(
            title="Settings",
            description=(
                "Configure system settings and\n"
                "automation preferences."
            ),
            icon="cog",
            command=self.open_settings,
        )

        cards_layout.addWidget(
            self.settings_card,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        # =====================================================
        # AUTOMATION CARD
        # =====================================================

        self.automation_card = self.create_card(
            title="Automation",
            description=(
                "Start the supplier automation\n"
                "and open the Msetu portal."
            ),
            icon="automation",
            command=self.start_automation,
            button_text="Start   →",
        )

        cards_layout.addWidget(
            self.automation_card,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        cards_layout.addStretch(1)

        content_layout.addWidget(
            cards_container,
            1,
        )

        # =====================================================
        # FOOTER
        # =====================================================

        self.footer = QLabel(
            "© 2025 HSI Automation Portal. All rights reserved."
        )

        self.footer.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.footer.setFixedHeight(35)

        self.footer.setStyleSheet(
            f"""
            QLabel {{
                color: {self.TEXT_GREY};
                background: {self.BG_COLOR};
                border: none;
                font-size: 9px;
            }}
            """
        )

        content_layout.addWidget(self.footer)

        root.addWidget(
            self.content,
            1,
        )

    def set_logo_fallback(self):
        self.logo_label.setText(
            "HSI\nAUTOMATION PORTAL"
        )

        self.logo_label.setStyleSheet(
            """
            QLabel {
                color: #10182D;
                background: transparent;
                border: none;
                font-size: 17px;
                font-weight: bold;
            }
            """
        )

    # =========================================================
    # CREATE CARD
    # =========================================================

    def create_card(
        self,
        title,
        description,
        icon,
        command,
        button_text="Open   →",
    ):

        card = QFrame()
        card.setFixedSize(
            285,
            260,
        )

        card.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )

        card.setStyleSheet(
            f"""
            QFrame {{
                background: {self.CARD_COLOR};
                border: none;
                border-radius: 16px;
            }}
            """
        )

        layout = QVBoxLayout(card)

        layout.setContentsMargins(
            15,
            25,
            15,
            20,
        )

        layout.setSpacing(0)

        # -----------------------------------------------------
        # ICON BACKGROUND
        # -----------------------------------------------------

        icon_frame = QFrame()
        icon_frame.setFixedSize(
            66,
            66,
        )

        icon_frame.setStyleSheet(
            f"""
            QFrame {{
                background: {self.ICON_BG};
                border: none;
                border-radius: 33px;
            }}
            """
        )

        icon_layout = QVBoxLayout(
            icon_frame
        )

        icon_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        icon_label = self.create_icon(
            icon,
            size=30,
            color=self.PRIMARY,
        )

        icon_layout.addWidget(
            icon_label
        )

        layout.addWidget(
            icon_frame,
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )

        layout.addSpacing(10)

        # -----------------------------------------------------
        # TITLE
        # -----------------------------------------------------

        title_label = QLabel(
            title
        )

        title_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        title_label.setStyleSheet(
            f"""
            QLabel {{
                color: {self.TEXT_DARK};
                background: transparent;
                border: none;
                font-size: 28px;
                font-weight: bold;
            }}
            """
        )

        layout.addWidget(
            title_label
        )

        layout.addSpacing(4)

        # -----------------------------------------------------
        # DESCRIPTION
        # -----------------------------------------------------

        description_label = QLabel(
            description
        )

        description_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        description_label.setStyleSheet(
            f"""
            QLabel {{
                color: {self.TEXT_GREY};
                background: transparent;
                border: none;
                font-size: 12px;
            }}
            """
        )

        layout.addWidget(
            description_label
        )

        layout.addSpacing(18)

        # -----------------------------------------------------
        # OPEN BUTTON
        # -----------------------------------------------------

        open_button = QPushButton(
            button_text
        )

        open_button.setFixedSize(
            105,
            38,
        )

        open_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        open_button.setStyleSheet(
            f"""
            QPushButton {{
                background: {self.PRIMARY};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                font-size: 11px;
            }}

            QPushButton:hover {{
                background: #0E48C7;
            }}

            QPushButton:pressed {{
                background: #0B3BA5;
            }}
            """
        )

        open_button.clicked.connect(
            command
        )

        layout.addWidget(
            open_button,
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )

        return card

    # =========================================================
    # GET USERNAME
    # =========================================================

    def get_username(self):

        try:
            return str(
                self.user.Username
            )

        except Exception:

            try:
                return str(
                    self.user[1]
                )

            except Exception:
                return "Admin User"

    # =========================================================
    # GET ROLE
    # =========================================================

    def get_role(self):

        try:
            return str(
                self.user.Role
            )

        except Exception:

            try:
                return str(
                    self.user[3]
                )

            except Exception:
                return "Administrator"

    # =========================================================
    # OPEN USER MASTER
    # =========================================================

    def open_user_master(self):

        print("User Master clicked")

        main_window = self.window()

        try:
            page = UserMasterPage(
                main_window,
                self.show_dashboard,
            )

            self.user_master_page = page

            # IMPORTANT:
            # Keep DashboardPage alive as the QMainWindow central widget.
            # User Master is displayed as an overlay child of the main window.
            # This prevents Qt from deleting DashboardPage when navigating.
            page.setParent(main_window)
            page.setGeometry(main_window.rect())
            page.show()
            page.raise_()

            self.hide()

        except Exception as error:
            print("User Master open error:", repr(error))
            self.user_master_page = None
            self.show()
            self.raise_()

    # =========================================================
    # SHOW DASHBOARD
    # =========================================================

    def show_dashboard(self):

        print("Back to Dashboard from User Master")

        if self.user_master_page is not None:
            page = self.user_master_page
            self.user_master_page = None

            page.close()
            page.deleteLater()

        # Dashboard remains the original central widget.
        # Only make it visible again.
        self.show()
        self.raise_()

    # =========================================================
    # RESIZE
    # =========================================================

    def resizeEvent(self, event):

        super().resizeEvent(event)

        # User Master, Mail Master and Settings are real central widgets,
        # so QMainWindow resizes them automatically.
        if self.automation_page is not None:
            self.automation_page.setGeometry(
                self.window().rect()
            )

    # =========================================================
    # MAIL MASTER
    # =========================================================

    def open_mail_master(self):

        print("Mail Master clicked")

        main_window = self.window()

        try:
            from mail_master_page import MailMasterPage

            page = MailMasterPage(
                main_window,
                self.show_mail_master_dashboard,
            )

            self.mail_master_page = page

            # Keep DashboardPage alive and show Mail Master over it.
            page.setParent(main_window)
            page.setGeometry(main_window.rect())
            page.show()
            page.raise_()

            self.hide()

        except Exception as error:
            print("Mail Master open error:", repr(error))
            self.mail_master_page = None
            self.show()
            self.raise_()

    def show_mail_master_dashboard(self):

        print("Back to Dashboard from Mail Master")

        if self.mail_master_page is not None:
            page = self.mail_master_page
            self.mail_master_page = None

            page.close()
            page.deleteLater()

        self.show()
        self.raise_()

    # =========================================================
    # SETTINGS
    # =========================================================

    def open_settings(self):

        print("Settings clicked")

        main_window = self.window()

        try:
            page = SettingsPage(
                main_window,
                self.show_settings_dashboard,
            )

            self.settings_page = page

            # IMPORTANT:
            # Do not call main_window.setCentralWidget(page).
            # Dashboard must remain alive as the central widget.
            page.setParent(main_window)
            page.setGeometry(main_window.rect())
            page.show()
            page.raise_()

            self.hide()

        except Exception as error:
            print("Settings open error:", repr(error))
            self.settings_page = None
            self.show()
            self.raise_()

    def show_settings_dashboard(self):

        print("Back to Dashboard from Settings")

        if self.settings_page is not None:
            page = self.settings_page
            self.settings_page = None

            page.close()
            page.deleteLater()

        # Dashboard is still the original central widget.
        self.show()
        self.raise_()

    # =========================================================
    # MAHINDRA PRELOAD
    # =========================================================

    def preload_mahindra(self):
        """
        Start the Mahindra Supplier Portal in a hidden WebEngineView.

        This avoids making the user wait for Chromium/WebEngine startup
        after clicking Automation -> Start.
        """
        if self.preload_browser is not None:
            return

        try:
            supplier_url = "https://supplier.mahindra.com/login"
            main_window = self.window()

            self.preload_page = EmbeddedBrowserPage(main_window)

            try:
                self.preload_page.profile().setHttpUserAgent(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0"
                )
            except Exception as ua_error:
                print("Mahindra preload User-Agent warning:", repr(ua_error))

            self.preload_browser = QWebEngineView(main_window)
            self.preload_browser.setPage(self.preload_page)

            # Keep it outside the visible UI while it loads in the
            # background. NOTE: because we call hide() explicitly here,
            # Qt will keep this widget hidden even after it is later
            # reparented into the automation page's layout - it must be
            # shown explicitly again in start_automation() when reused.
            self.preload_browser.setGeometry(-2000, -2000, 1200, 800)
            self.preload_browser.hide()

            # Capture the actual view object here (not self.preload_browser).
            # start_automation() sets self.preload_browser = None once it
            # reuses this same widget as self.supplier_browser, but the
            # widget itself keeps firing loadFinished on later navigations
            # (e.g. an SSO redirect). Reading self.preload_browser inside
            # the callback would then crash with AttributeError on None.
            preload_view = self.preload_browser

            def preload_finished(ok):
                self.preload_ready = bool(ok)
                print(
                    "Mahindra preload finished:",
                    ok,
                    "URL:",
                    preload_view.url().toString()
                )

            self.preload_browser.loadFinished.connect(preload_finished)

            self.preload_browser.renderProcessTerminated.connect(
                lambda status, exit_code: print(
                    "Mahindra preload WebEngine process terminated:",
                    status,
                    exit_code,
                )
            )

            self.preload_browser.setUrl(QUrl(supplier_url))
            print("Mahindra preload started:", supplier_url)

        except Exception as error:
            print("Mahindra preload error:", repr(error))
            self.preload_browser = None
            self.preload_page = None
            self.preload_ready = False

    # =========================================================
    # EMBEDDED MAHINDRA AUTOMATION
    # =========================================================

    def start_automation(self):
        """
        Open the Mahindra Supplier Portal INSIDE this HSI application.

        Important:
        - No Selenium Edge/Chrome window is created.
        - QWebEngineView is used for the Mahindra portal.
        - OTP is still read from the configured mailbox using IMAP.
        - JavaScript inside QWebEngine fills the OTP and clicks Verify OTP.
        """
        if getattr(self, "automation_page", None) is not None:
            self.automation_page.show()
            self.automation_page.raise_()
            self.hide()
            return

        try:
            main_window = self.window()

            self.automation_page = QFrame(main_window)
            self.automation_page.setStyleSheet("""
                QFrame {
                    background: #FFFFFF;
                    border: none;
                }
            """)
            self.automation_page.setGeometry(main_window.rect())

            automation_layout = QVBoxLayout(self.automation_page)
            automation_layout.setContentsMargins(0, 0, 0, 0)
            automation_layout.setSpacing(0)

            # ---------------------------------------------------------
            # Automation top bar
            # ---------------------------------------------------------
            top_bar = QFrame()
            top_bar.setFixedHeight(45)
            top_bar.setStyleSheet("""
                QFrame {
                    background: #FFFFFF;
                    border-bottom: 1px solid #E2E8F0;
                }
            """)

            top_layout = QHBoxLayout(top_bar)
            top_layout.setContentsMargins(14, 6, 14, 6)
            top_layout.setSpacing(8)

            title = QLabel("Mahindra Supplier Portal")
            title.setStyleSheet("""
                QLabel {
                    color: #10182D;
                    background: transparent;
                    border: none;
                    font-size: 14px;
                    font-weight: bold;
                }
            """)
            top_layout.addWidget(title)
            top_layout.addStretch()

            self.automation_status = QLabel("Loading...")
            self.automation_status.setStyleSheet("""
                QLabel {
                    color: #71809E;
                    background: transparent;
                    border: none;
                    font-size: 10px;
                }
            """)
            top_layout.addWidget(self.automation_status)

            back_button = QPushButton("← Back")
            back_button.setFixedSize(85, 32)
            back_button.setCursor(Qt.CursorShape.PointingHandCursor)
            back_button.setStyleSheet("""
                QPushButton {
                    background: #1457E6;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover { background: #0E48C7; }
                QPushButton:pressed { background: #0B3BA5; }
            """)
            back_button.clicked.connect(self.show_automation_dashboard)
            top_layout.addWidget(back_button)

            automation_layout.addWidget(top_bar)

            # ---------------------------------------------------------
            # Reuse the preloaded browser if available.
            # Otherwise create a new embedded browser.
            # ---------------------------------------------------------
            browser = self.preload_browser

            if browser is not None:
                self.supplier_browser = browser
                self.preload_browser = None
                self.preload_page = None
                browser.setParent(self.automation_page)
            else:
                self.web_page = EmbeddedBrowserPage(self.automation_page)
                self.supplier_browser = QWebEngineView(self.automation_page)
                self.supplier_browser.setPage(self.web_page)

            self.supplier_browser.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )
            self.supplier_browser.setStyleSheet("border: none;")
            automation_layout.addWidget(self.supplier_browser, 1)

            # ---------------------------------------------------------
            # Show embedded browser
            # ---------------------------------------------------------
            self.automation_page.show()
            self.automation_page.raise_()
            self.supplier_browser.show()
            self.supplier_browser.raise_()
            self.hide()

            # ---------------------------------------------------------
            # Reset automation state
            # ---------------------------------------------------------
            self.otp_started = False
            self.otp_verify_clicked = False
            self.otp_value = None
            self.otp_worker_result = None
            self.otp_fetch_in_progress = False
            self.otp_fetch_worker_running = False
            self.otp_wait_started = None
            self.otp_baseline_ready = False
            self.otp_popup_detected = False
            self.mahindra_dashboard_detected = False
            self._embedded_login_retry_count = 0

            # Connect loadFinished only once for this browser instance.
            if not getattr(self, "_embedded_load_connected", False):
                self.supplier_browser.loadFinished.connect(
                    self._embedded_load_finished
                )
                self._embedded_load_connected = True

            self.automation_status.setText("Opening Mahindra portal...")

            # If the reused preload has already navigated somewhere, force the
            # login URL. For a new browser this also starts the navigation.
            supplier_url = "https://supplier.mahindra.com/login"
            current_url = self.supplier_browser.url().toString().lower()

            if "supplier.mahindra.com" not in current_url:
                self.supplier_browser.setUrl(QUrl(supplier_url))
            elif "/login" not in current_url:
                self.supplier_browser.setUrl(QUrl(supplier_url))
            else:
                # Already on login page; start after the Angular UI renders.
                QTimer.singleShot(1500, self._embedded_prepare_login)

        except Exception as error:
            print("Embedded Mahindra browser error:", repr(error))
            self._cleanup_embedded_browser()
            self.show()
            self.raise_()

    def _embedded_load_finished(self, ok):
        """Handle QWebEngine navigation completion."""
        if not getattr(self, "automation_page", None):
            return

        if not ok:
            self.automation_status.setText(
                "Mahindra page failed to load"
            )
            return

        url = self.supplier_browser.url().toString()
        print("Mahindra embedded page loaded:", url)

        self.automation_status.setText("Mahindra portal loaded")

        # Give Angular Material enough time to render its controls.
        QTimer.singleShot(1200, self._embedded_prepare_login)

    def _embedded_prepare_login(self):
        """
        Capture the current mailbox state and then click Supplier User Login
        from inside QWebEngine.
        """
        if self.supplier_browser is None:
            return

        if getattr(self, "otp_started", False):
            return

        if getattr(self, "otp_baseline_worker_running", False):
            return

        self.automation_status.setText("Preparing Supplier User Login...")
        self.otp_baseline_worker_running = True
        self.otp_baseline_result = None

        def worker():
            try:
                result = self._get_mail_uids()
            except Exception as error:
                print("OTP baseline error:", repr(error))
                result = set()
            self.otp_baseline_result = result
            self.otp_baseline_worker_running = False

        threading.Thread(target=worker, daemon=True).start()
        QTimer.singleShot(250, self._embedded_wait_for_baseline)

    def _embedded_wait_for_baseline(self):
        """Wait for mailbox baseline and then click Supplier User Login."""
        if self.supplier_browser is None:
            return

        if getattr(self, "otp_baseline_worker_running", False):
            QTimer.singleShot(250, self._embedded_wait_for_baseline)
            return

        if getattr(self, "otp_baseline_result", None) is None:
            QTimer.singleShot(250, self._embedded_wait_for_baseline)
            return

        self.otp_baseline_ready = True
        self.otp_baseline_uids = self.otp_baseline_result
        self.otp_baseline_result = None
        self.otp_baseline_worker_running = False

        self.otp_started = True
        self.otp_wait_started = datetime.now(timezone.utc)

        self.automation_status.setText(
            "Clicking Supplier User Login..."
        )

        js = """
        (() => {
            const normalize = value =>
                (value || '').replace(/\\s+/g, ' ').trim().toLowerCase();

            const candidates = Array.from(
                document.querySelectorAll('button, input, [role="button"]')
            );

            const target = candidates.find(el => {
                const text = normalize(
                    el.innerText || el.textContent || el.value || el.getAttribute('aria-label')
                );
                return text.includes('supplier user login');
            });

            if (!target) {
                return {ok: false, reason: 'Supplier User Login not found'};
            }

            target.scrollIntoView({block: 'center', inline: 'center'});
            target.click();
            return {ok: true};
        })();
        """

        self.supplier_browser.page().runJavaScript(
            js,
            self._embedded_supplier_login_clicked
        )

    def _embedded_supplier_login_clicked(self, result):
        print("Supplier User Login JS result:", result)

        if isinstance(result, dict) and result.get("ok"):
            self.automation_status.setText(
                "Waiting for OTP popup..."
            )
            self._start_embedded_otp_popup_poll()
            return

        # Angular may not have rendered the button yet. Retry a few times.
        self._embedded_login_retry_count = getattr(
            self, "_embedded_login_retry_count", 0
        ) + 1

        if self._embedded_login_retry_count <= 20:
            QTimer.singleShot(750, self._embedded_prepare_login)
        else:
            self.automation_status.setText(
                "Supplier User Login button not found"
            )
            print("Could not find Supplier User Login in QWebEngine.")

    def _start_embedded_otp_popup_poll(self):
        self.otp_popup_detected = False
        self.otp_popup_poll_count = 0
        QTimer.singleShot(300, self._poll_embedded_otp_popup)

    def _poll_embedded_otp_popup(self):
        """Detect app-otp-input and start mailbox OTP retrieval."""
        if self.supplier_browser is None:
            return

        if self.otp_popup_detected:
            return

        self.otp_popup_poll_count += 1

        js = """
        (() => {
            const component = document.querySelector('app-otp-input');
            if (!component) return false;
            const inputs = component.querySelectorAll('input');
            return component.offsetParent !== null && inputs.length >= 6;
        })();
        """

        self.supplier_browser.page().runJavaScript(
            js,
            self._embedded_otp_popup_result
        )

        if self.otp_popup_poll_count < 80:
            QTimer.singleShot(500, self._poll_embedded_otp_popup)
        else:
            self.automation_status.setText(
                "OTP popup was not detected"
            )

    def _embedded_otp_popup_result(self, visible):
        if visible and not self.otp_popup_detected:
            self.otp_popup_detected = True
            self.automation_status.setText(
                "OTP popup detected. Waiting for email..."
            )
            print("Mahindra OTP popup detected inside QWebEngine.")
            self._start_embedded_otp_worker()

    def _start_embedded_otp_worker(self):
        if getattr(self, "otp_fetch_worker_running", False):
            return

        self.otp_fetch_worker_running = True
        self.otp_worker_result = None

        baseline = set(getattr(self, "otp_baseline_uids", set()))

        def worker():
            try:
                otp = self._wait_for_new_otp_email(
                    baseline_uids=baseline,
                    timeout=110,
                    poll_seconds=3,
                )
                self.otp_worker_result = otp
            except Exception as error:
                print("Embedded OTP worker error:", repr(error))
                self.otp_worker_result = None
            finally:
                self.otp_fetch_worker_running = False

        threading.Thread(target=worker, daemon=True).start()
        QTimer.singleShot(300, self._check_embedded_otp_worker)

    def _check_embedded_otp_worker(self):
        if self.supplier_browser is None:
            return

        if getattr(self, "otp_fetch_worker_running", False):
            QTimer.singleShot(300, self._check_embedded_otp_worker)
            return

        otp = self.otp_worker_result
        self.otp_worker_result = None

        if not otp:
            self.automation_status.setText(
                "OTP email was not received"
            )
            return

        self.otp_value = str(otp)
        self.automation_status.setText(
            "OTP received. Verifying..."
        )

        self._embedded_fill_otp(self.otp_value)

    def _embedded_fill_otp(self, otp):
        """Fill six OTP fields and click Verify OTP using page JavaScript."""
        import json

        otp = str(otp).strip()

        if len(otp) != 6 or not otp.isdigit():
            print("Invalid OTP:", repr(otp))
            self.automation_status.setText("Invalid OTP received")
            return

        otp_js = json.dumps(otp)

        js = f"""
        (otp => {{
            const component = document.querySelector('app-otp-input');

            if (!component) {{
                return {{ok:false, reason:'OTP component not found'}};
            }}

            const inputs = Array.from(component.querySelectorAll('input'))
                .filter(el => el.offsetParent !== null)
                .slice(0, 6);

            if (inputs.length < 6) {{
                return {{ok:false, reason:'Six OTP inputs not found'}};
            }}

            inputs.forEach((input, index) => {{
                const value = otp[index];
                input.focus();

                const descriptor = Object.getOwnPropertyDescriptor(
                    HTMLInputElement.prototype,
                    'value'
                );

                if (descriptor && descriptor.set) {{
                    descriptor.set.call(input, value);
                }} else {{
                    input.value = value;
                }}

                input.dispatchEvent(new Event('input', {{bubbles:true}}));
                input.dispatchEvent(new Event('change', {{bubbles:true}}));
                input.dispatchEvent(new KeyboardEvent('keyup', {{
                    key: value,
                    bubbles: true
                }}));
            }});

            const buttons = Array.from(
                component.querySelectorAll(
                    'button, input[type="button"], input[type="submit"]'
                )
            );

            const verify = buttons.find(el => {{
                const text = (
                    el.innerText || el.textContent || el.value || ''
                ).trim().toLowerCase();

                return text.includes('verify otp') ||
                       text === 'verify' ||
                       text.includes('verify');
            }});

            if (!verify) {{
                return {{ok:false, reason:'Verify OTP button not found'}};
            }}

            verify.scrollIntoView({{block:'center'}});

            setTimeout(() => verify.click(), 150);

            return {{ok:true}};
        }})({otp_js});
        """

        self.supplier_browser.page().runJavaScript(
            js,
            self._embedded_otp_filled
        )

    def _embedded_otp_filled(self, result):
        print("Embedded OTP result:", result)

        if isinstance(result, dict) and result.get("ok"):
            self.otp_verify_clicked = True
            self.automation_status.setText(
                "OTP verified. Opening Mahindra dashboard..."
            )
            self._start_embedded_dashboard_poll()
        else:
            self.automation_status.setText(
                "Could not verify OTP"
            )
            print("Embedded OTP verification failed:", result)

    def _start_embedded_dashboard_poll(self):
        self.dashboard_poll_count = 0
        QTimer.singleShot(700, self._poll_embedded_dashboard)

    def _poll_embedded_dashboard(self):
        if self.supplier_browser is None:
            return

        self.dashboard_poll_count += 1

        js = """
        (() => {
            const url = window.location.href.toLowerCase();
            const body = (document.body?.innerText || '').toLowerCase();

            return {
                url: url,
                ready: url.includes('/dashboard') ||
                       body.includes('supplier dashboard') ||
                       body.includes('dashboard')
            };
        })();
        """

        self.supplier_browser.page().runJavaScript(
            js,
            self._embedded_dashboard_result
        )

    def _embedded_dashboard_result(self, result):
        if isinstance(result, dict) and result.get("ready"):
            self.mahindra_dashboard_detected = True
            self.automation_status.setText(
                "Mahindra dashboard ready"
            )
            print(
                "Mahindra dashboard opened inside HSI:",
                result.get("url", "")
            )
            return

        if getattr(self, "dashboard_poll_count", 0) < 90:
            QTimer.singleShot(700, self._poll_embedded_dashboard)
        else:
            self.automation_status.setText(
                "Dashboard detection timed out"
            )

    # =========================================================
    # IMAP - GET CURRENT MESSAGE UIDS
    # =========================================================

    def _get_mail_uids(self):
        """Return all current INBOX UIDs without reading message bodies."""
        mail = None

        try:
            mail = imaplib.IMAP4_SSL(
                OTP_MAIL_SERVER,
                OTP_MAIL_PORT,
                timeout=20,
            )

            mail.login(
                OTP_MAIL_USERNAME,
                OTP_MAIL_PASSWORD,
            )

            status, _ = mail.select("INBOX")
            if status != "OK":
                print("Could not select OTP INBOX.")
                return set()

            status, data = mail.uid("search", None, "ALL")
            if status != "OK" or not data or not data[0]:
                return set()

            return set(data[0].split())

        except Exception as error:
            print("Could not get OTP mailbox UIDs:", repr(error))
            return set()

        finally:
            try:
                if mail is not None:
                    mail.logout()
            except Exception:
                pass

    # =========================================================
    # IMAP - WAIT FOR NEW OTP
    # =========================================================

    def _wait_for_new_otp_email(
        self,
        baseline_uids,
        timeout=110,
        poll_seconds=3,
    ):
        """Wait for the fresh six-digit Mahindra OTP email."""
        started = time.time()
        attempt = 0

        while time.time() - started < timeout:
            attempt += 1
            print(f"Checking OTP email... attempt #{attempt}")

            otp = self._read_newest_otp_from_mailbox(baseline_uids)
            if otp:
                return otp

            time.sleep(poll_seconds)

        return None

    def _read_newest_otp_from_mailbox(self, baseline_uids):
        """Read the newest fresh six-digit Mahindra OTP from INBOX."""
        mail = None

        try:
            mail = imaplib.IMAP4_SSL(
                OTP_MAIL_SERVER,
                OTP_MAIL_PORT,
                timeout=20,
            )

            mail.login(
                OTP_MAIL_USERNAME,
                OTP_MAIL_PASSWORD,
            )

            status, _ = mail.select("INBOX")
            if status != "OK":
                print("OTP mailbox INBOX select failed.")
                return None

            status, data = mail.uid("search", None, "ALL")
            if status != "OK" or not data or not data[0]:
                print("OTP mailbox search returned no messages.")
                return None

            current_uids = data[0].split()
            new_uids = [
                uid for uid in current_uids
                if uid not in baseline_uids
            ]

            ordered_uids = []

            for uid in reversed(new_uids[-20:]):
                if uid not in ordered_uids:
                    ordered_uids.append(uid)

            for uid in reversed(current_uids[-20:]):
                if uid not in ordered_uids:
                    ordered_uids.append(uid)

            login_time = getattr(
                self,
                "otp_wait_started",
                None,
            )

            if login_time is None:
                login_time = datetime.now(timezone.utc)

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

                    body = self._get_email_body(msg)
                    body_text = self._normalise_email_text(body)

                    print(
                        f"OTP candidate: UID={uid!r}, "
                        f"From={sender!r}, Subject={subject!r}"
                    )

                    is_new_uid = uid not in baseline_uids
                    message_is_fresh = is_new_uid

                    if not message_is_fresh:
                        try:
                            message_date = msg.get("Date", "")
                            parsed_date = parsedate_to_datetime(
                                message_date
                            )

                            if parsed_date.tzinfo is None:
                                parsed_date = parsed_date.replace(
                                    tzinfo=timezone.utc
                                )
                            else:
                                parsed_date = parsed_date.astimezone(
                                    timezone.utc
                                )

                            message_is_fresh = (
                                parsed_date >= freshness_time
                            )

                        except Exception as date_error:
                            print(
                                "OTP Date parse warning:",
                                repr(date_error),
                            )

                    if not message_is_fresh:
                        continue

                    sender_lower = sender.lower()
                    subject_lower = subject.lower()
                    body_lower = body_text.lower()

                    sender_matches = (
                        "mahindra" in sender_lower
                        or "msetu" in sender_lower
                        or "mahindramail.com" in sender_lower
                        or OTP_SENDER.lower() in sender_lower
                    )

                    subject_matches = (
                        "otp" in subject_lower
                        or "msetu" in subject_lower
                        or "logon" in subject_lower
                        or "login" in subject_lower
                        or "one time" in subject_lower
                    )

                    body_matches = (
                        "otp" in body_lower
                        or "one time password" in body_lower
                        or "verification code" in body_lower
                    )

                    six_digits = re.findall(
                        r"(?<!\d)\d{6}(?!\d)",
                        body_text,
                    )

                    spaced_otp_matches = re.findall(
                        r"(?<!\d)"
                        r"(\d\s*\d\s*\d\s*\d\s*\d\s*\d)"
                        r"(?!\d)",
                        body_text,
                    )

                    spaced_otps = [
                        re.sub(r"\s+", "", value)
                        for value in spaced_otp_matches
                    ]

                    if not six_digits and not spaced_otps:
                        continue

                    if not (
                        sender_matches
                        or subject_matches
                        or body_matches
                    ):
                        print(
                            "Fresh email contains OTP but does not "
                            "look like Mahindra; skipping."
                        )
                        continue

                    otp_patterns = [
                        r"(?:OTP|One\s*Time\s*Password)\s*"
                        r"(?:for\s+(?:this\s+)?(?:login|logon)\s*)?"
                        r"(?:is|:|code)?\s*[:\-]?\s*(\d{6})",
                        r"(?:verification|authentication)\s+"
                        r"(?:OTP|code)\s*(?:is|:)?\s*[:\-]?\s*(\d{6})",
                    ]

                    for pattern in otp_patterns:
                        match = re.search(
                            pattern,
                            body_text,
                            re.IGNORECASE | re.DOTALL,
                        )

                        if match:
                            return match.group(1)

                    if six_digits:
                        return six_digits[-1]

                    if spaced_otps:
                        return spaced_otps[-1]

                except Exception as message_error:
                    print(
                        "OTP message read error:",
                        repr(message_error),
                    )
                    continue

            return None

        except Exception as error:
            print("OTP mailbox read error:", repr(error))
            return None

        finally:
            try:
                if mail is not None:
                    mail.logout()
            except Exception:
                pass

    # =========================================================
    # EMAIL HELPERS
    # =========================================================

    @staticmethod
    def _decode_email_header(value):
        """Decode a MIME email header safely."""
        if not value:
            return ""

        try:
            parts = decode_header(str(value))
            decoded = []

            for part, encoding in parts:
                if isinstance(part, bytes):
                    try:
                        decoded.append(
                            part.decode(encoding or "utf-8", errors="replace")
                        )
                    except Exception:
                        decoded.append(
                            part.decode("utf-8", errors="replace")
                        )
                else:
                    decoded.append(str(part))

            return "".join(decoded)

        except Exception:
            return str(value)

    @staticmethod
    def _get_email_body(message):
        """Return plain-text email body, preferring text/plain."""
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

                    if content_type == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            plain_parts.append(
                                payload.decode(charset, errors="replace")
                            )

                    elif content_type == "text/html":
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            html_parts.append(
                                payload.decode(charset, errors="replace")
                            )

                if plain_parts:
                    return "\n".join(plain_parts)

                if html_parts:
                    return "\n".join(html_parts)

                return ""

            payload = message.get_payload(decode=True)

            if payload is None:
                value = message.get_payload()
                return value if isinstance(value, str) else ""

            charset = message.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")

        except Exception as error:
            print("Email body decode error:", repr(error))
            return ""

    @staticmethod
    def _normalise_email_text(text):
        """Convert HTML-ish/email whitespace into searchable plain text."""
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
        text = re.sub(r"&nbsp;", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"&amp;", "&", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    # =========================================================
    # EMBEDDED BROWSER CLEANUP / BACK
    # =========================================================

    def _cleanup_embedded_browser(self):
        """Hide and release the embedded Mahindra page."""
        try:
            if self.supplier_browser is not None:
                self.supplier_browser.hide()
                self.supplier_browser.deleteLater()
        except Exception:
            pass

        self.supplier_browser = None
        self.web_page = None
        self.automation_page = None
        self._embedded_load_connected = False

        self.otp_started = False
        self.otp_verify_clicked = False
        self.otp_value = None
        self.otp_popup_detected = False
        self.mahindra_dashboard_detected = False

    def show_automation_dashboard(self):
        """Return from Mahindra embedded browser to the HSI dashboard."""
        print("Back to HSI Dashboard from Mahindra")

        try:
            if self.automation_page is not None:
                self.automation_page.hide()

            if self.supplier_browser is not None:
                self.supplier_browser.hide()

            self.show()
            self.raise_()

        except Exception as error:
            print("Return dashboard error:", repr(error))
            self.show()
            self.raise_()

    # =========================================================
    # LOGOUT
    # =========================================================

    def logout(self):

        if callable(
            self.logout_callback
        ):
            self.logout_callback()


# =============================================================
# OPTIONAL STANDALONE TEST
# =============================================================

if __name__ == "__main__":

    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow

    app = QApplication(
        sys.argv
    )

    app.setStyle(
        "Fusion"
    )

    window = QMainWindow()
    window.setWindowTitle(
        "HSI Automation Portal"
    )
    window.resize(
        1347,
        758
    )
    window.setMinimumSize(
        1250,
        620
    )

    dashboard = DashboardPage(
        window,
        user=None,
        logout_callback=window.close,
    )

    window.setCentralWidget(
        dashboard
    )

    window.show()

    sys.exit(
        app.exec()
    )
