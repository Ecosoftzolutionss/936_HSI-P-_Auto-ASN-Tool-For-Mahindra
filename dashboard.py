from pathlib import Path

from PyQt6.QtCore import Qt, QByteArray
from PyQt6.QtGui import QPixmap, QIcon, QImage, QPainter
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtSvg import QSvgRenderer

from user_master import UserMasterPage
from settings import SettingsPage

# Mahindra Supplier Portal automation runs in a separate Microsoft Edge
# browser window. The HSI dashboard does not embed the supplier portal.
from automation import AutomationController


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

        self.user = user
        self.logout_callback = logout_callback

        self.base_path = Path(__file__).resolve().parent
        self.user_master_page = None
        self.mail_master_page = None
        self.settings_page = None

        # Created lazily the first time the Automation card is opened.
        self.automation = None

        self.setStyleSheet(
            f"""
            QWidget {{
                font-family: "Segoe UI";
                color: {self.TEXT_DARK};
            }}
            """
        )

        self.create_ui()

        # The Mahindra WebEngine is only started when Automation is clicked.
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
            "user": "\u25cf",
            "users": "\U0001f465",
            "mail": "\u2709",
            "cog": "\u2699",
            "sign-out-alt": "\u21aa",
            "arrow-right": "\u2192",
            "automation": "\u2699",
        }

        label = QLabel(icons.get(name, "\u2022"))
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
        self.user_area.setStyleSheet(
            """
            QFrame {
                background: transparent;
                border: none;
            }
            """
        )

        user_layout = QHBoxLayout(self.user_area)
        user_layout.setContentsMargins(0, 0, 0, 0)
        user_layout.setSpacing(0)

        # User icon circle
        self.user_icon_frame = QFrame()
        self.user_icon_frame.setFixedSize(32, 32)
        self.user_icon_frame.setStyleSheet(
            """
            QFrame {
                background: #EEF4FF;
                border: none;
                border-radius: 16px;
            }
            """
        )

        icon_layout = QVBoxLayout(self.user_icon_frame)
        icon_layout.setContentsMargins(0, 0, 0, 0)

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
        self.user_icon_label.setPixmap(
            QPixmap.fromImage(self._render_svg(user_svg, 32, 32))
        )
        icon_layout.addWidget(self.user_icon_label)

        user_layout.addWidget(self.user_icon_frame)
        user_layout.addSpacing(8)

        # Username + role stacked vertically
        user_text_frame = QFrame()
        user_text_frame.setFixedWidth(82)
        user_text_frame.setStyleSheet(
            """
            QFrame {
                background: transparent;
                border: none;
            }
            """
        )

        user_text_layout = QVBoxLayout(user_text_frame)
        user_text_layout.setContentsMargins(0, 0, 0, 0)
        user_text_layout.setSpacing(1)
        user_text_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        username = self.get_username()
        role = self.get_role()

        self.user_name_label = QLabel(username)
        self.user_name_label.setStyleSheet(
            f"""
            QLabel {{
                color: {self.TEXT_DARK};
                background: transparent;
                border: none;
                font-size: 10px;
                font-weight: bold;
            }}
            """
        )
        self.user_name_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        self.role_label = QLabel(role)
        self.role_label.setStyleSheet(
            f"""
            QLabel {{
                color: {self.TEXT_GREY};
                background: transparent;
                border: none;
                font-size: 7px;
            }}
            """
        )
        self.role_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        user_text_layout.addWidget(self.user_name_label)
        user_text_layout.addWidget(self.role_label)

        user_layout.addWidget(user_text_frame)

        # Small dropdown arrow
        self.profile_arrow = QLabel("\u2304")
        self.profile_arrow.setFixedSize(16, 30)
        self.profile_arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.profile_arrow.setStyleSheet(
            """
            QLabel {
                color: #64748B;
                background: transparent;
                border: none;
                font-size: 13px;
            }
            """
        )
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

        self.logout_button.setIcon(
            QIcon(QPixmap.fromImage(self._render_svg(logout_svg, 32, 32)))
        )
        self.logout_button.setIconSize(self.logout_button.size())
        self.logout_button.setStyleSheet(
            """
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
            """
        )

        self.logout_button.clicked.connect(self.logout)
        user_layout.addWidget(self.logout_button)

        header_layout.addWidget(self.user_area)

        root.addWidget(self.header)

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

        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 0, 0, 0)
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

        welcome_layout = QVBoxLayout(welcome_container)
        welcome_layout.setContentsMargins(35, 35, 35, 0)
        welcome_layout.setSpacing(0)

        # =====================================================
        # WELCOME
        # =====================================================

        self.welcome_label = QLabel(f"Welcome {self.get_username()}!")
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
        welcome_layout.addWidget(self.welcome_label)

        # =====================================================
        # DESCRIPTION
        # =====================================================

        self.description_label = QLabel("Select an option below to manage the system.")
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
        welcome_layout.addWidget(self.description_label)

        # =====================================================
        # BLUE LINE
        # =====================================================

        self.blue_line = QFrame()
        self.blue_line.setFixedSize(45, 3)
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
        welcome_layout.addWidget(self.blue_line)

        content_layout.addWidget(welcome_container)

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

        # ---------------------------------------------------
        # USER MASTER CARD
        # ---------------------------------------------------
        self.user_card = self.create_card(
            title="User Master",
            description=(
                "Manage users, roles and permissions\n"
                "for the HSI Automation Portal."
            ),
            icon="users",
            command=self.open_user_master,
        )
        cards_layout.addWidget(self.user_card, 0, Qt.AlignmentFlag.AlignTop)

        # ---------------------------------------------------
        # MAIL MASTER CARD
        # ---------------------------------------------------
        self.mail_master_card = self.create_card(
            title="Mail Master",
            description=(
                "Configure mail server and\n"
                "OTP email settings."
            ),
            icon="mail",
            command=self.open_mail_master,
        )
        cards_layout.addWidget(self.mail_master_card, 0, Qt.AlignmentFlag.AlignTop)

        # ---------------------------------------------------
        # SETTINGS CARD
        # ---------------------------------------------------
        self.settings_card = self.create_card(
            title="Settings",
            description=(
                "Configure system settings and\n"
                "automation preferences."
            ),
            icon="cog",
            command=self.open_settings,
        )
        cards_layout.addWidget(self.settings_card, 0, Qt.AlignmentFlag.AlignTop)

        # ---------------------------------------------------
        # AUTOMATION CARD
        # ---------------------------------------------------
        self.automation_card = self.create_card(
            title="Automation",
            description=(
                "Start the supplier automation\n"
                "and open the Msetu portal."
            ),
            icon="automation",
            command=self.start_automation,
            button_text="Start   \u2192",
        )
        cards_layout.addWidget(self.automation_card, 0, Qt.AlignmentFlag.AlignTop)

        cards_layout.addStretch(1)

        content_layout.addWidget(cards_container, 1)

        # =====================================================
        # FOOTER
        # =====================================================

        self.footer = QLabel("\u00a9 2025 HSI Automation Portal. All rights reserved.")
        self.footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
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

        root.addWidget(self.content, 1)

    def _render_svg(self, svg_text, width, height):
        """Small helper: rasterize an inline SVG string into a QImage."""
        image = QImage(width, height, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
        renderer.render(painter)
        painter.end()
        return image

    def set_logo_fallback(self):
        self.logo_label.setText("HSI\nAUTOMATION PORTAL")
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

    def create_card(self, title, description, icon, command, button_text="Open   \u2192"):

        card = QFrame()
        card.setFixedSize(285, 260)
        card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
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
        layout.setContentsMargins(15, 25, 15, 20)
        layout.setSpacing(0)

        # -----------------------------------------------------
        # ICON BACKGROUND
        # -----------------------------------------------------
        icon_frame = QFrame()
        icon_frame.setFixedSize(66, 66)
        icon_frame.setStyleSheet(
            f"""
            QFrame {{
                background: {self.ICON_BG};
                border: none;
                border-radius: 33px;
            }}
            """
        )

        icon_layout = QVBoxLayout(icon_frame)
        icon_layout.setContentsMargins(0, 0, 0, 0)

        icon_label = self.create_icon(icon, size=30, color=self.PRIMARY)
        icon_layout.addWidget(icon_label)

        layout.addWidget(icon_frame, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(10)

        # -----------------------------------------------------
        # TITLE
        # -----------------------------------------------------
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        layout.addWidget(title_label)
        layout.addSpacing(4)

        # -----------------------------------------------------
        # DESCRIPTION
        # -----------------------------------------------------
        description_label = QLabel(description)
        description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        layout.addWidget(description_label)
        layout.addSpacing(18)

        # -----------------------------------------------------
        # OPEN BUTTON
        # -----------------------------------------------------
        open_button = QPushButton(button_text)
        open_button.setFixedSize(105, 38)
        open_button.setCursor(Qt.CursorShape.PointingHandCursor)
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
        open_button.clicked.connect(command)

        layout.addWidget(open_button, 0, Qt.AlignmentFlag.AlignHCenter)

        return card

    # =========================================================
    # GET USERNAME / ROLE
    # =========================================================

    def get_username(self):
        try:
            return str(self.user.Username)
        except Exception:
            try:
                return str(self.user[1])
            except Exception:
                return "Admin User"

    def get_role(self):
        try:
            return str(self.user.Role)
        except Exception:
            try:
                return str(self.user[3])
            except Exception:
                return "Administrator"

    # =========================================================
    # USER MASTER
    # =========================================================

    def open_user_master(self):
        print("User Master clicked")

        main_window = self.window()

        try:
            page = UserMasterPage(main_window, self.show_dashboard)
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
    # MAIL MASTER
    # =========================================================

    def open_mail_master(self):
        print("Mail Master clicked")

        main_window = self.window()

        try:
            from mail_master_page import MailMasterPage

            page = MailMasterPage(main_window, self.show_mail_master_dashboard)
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
            page = SettingsPage(main_window, self.show_settings_dashboard)
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
    # AUTOMATION - EXTERNAL MICROSOFT EDGE
    # =========================================================

    def start_automation(self):
        """
        Start Mahindra automation in a separate Microsoft Edge window.

        The Mahindra Supplier Portal is NOT embedded in the HSI application.
        The HSI dashboard remains visible while Selenium controls Edge.
        """
        try:
            if self.automation is None:
                self.automation = AutomationController(
                    main_window=self.window(),
                    on_back=self.show,
                )

            # Start the real Microsoft Edge browser.
            # Do not raise HSI after starting Edge; doing so can cover Edge.
            self.automation.start()

            self.show()

            print("Mahindra automation started in external Edge.")

        except Exception as error:
            print("Automation start error:", repr(error))
            self.show()
            self.raise_()

    def close_automation(self):
        """Close the external Edge automation if it is running."""
        try:
            if self.automation is not None:
                self.automation.cleanup()
                self.automation = None
        except Exception as error:
            print("Automation cleanup error:", repr(error))

    # =========================================================
    # RESIZE
    # =========================================================

    def resizeEvent(self, event):
        # No Mahindra page is embedded in this window.
        super().resizeEvent(event)

    # =========================================================
    # LOGOUT
    # =========================================================

    def logout(self):
        # Close the external Edge automation before returning to login.
        self.close_automation()

        if callable(self.logout_callback):
            self.logout_callback()


# =============================================================
# OPTIONAL STANDALONE TEST
# =============================================================

if __name__ == "__main__":

    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = QMainWindow()
    window.setWindowTitle("HSI Automation Portal")
    window.resize(1347, 758)
    window.setMinimumSize(1250, 620)

    dashboard = DashboardPage(window, user=None, logout_callback=window.close)

    window.setCentralWidget(dashboard)
    window.show()

    sys.exit(app.exec())