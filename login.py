from pathlib import Path

import bcrypt

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from database import get_connection


class Toast(QWidget):
    """Small top-right toast notification."""

    def __init__(self, parent, message, message_type="success", duration=2500):
        super().__init__(parent)

        self.duration = duration
        self.setFixedSize(360, 76)

        colors = {
            "success": ("Success", "✓", "#22C55E"),
            "error": ("Error", "!", "#EF4444"),
            "warning": ("Warning", "!", "#F59E0B"),
        }

        title, icon_text, border_color = colors.get(
            message_type,
            colors["warning"],
        )

        self.setStyleSheet(
            """
            Toast {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
            }
            """
        )

        # Icon circle
        icon_frame = QFrame(self)
        icon_frame.setGeometry(14, 19, 36, 36)
        icon_frame.setStyleSheet(
            f"""
            QFrame {{
                background-color: {border_color};
                border-radius: 18px;
            }}
            """
        )

        icon_label = QLabel(icon_text, icon_frame)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setGeometry(0, 0, 36, 36)
        icon_label.setStyleSheet(
            """
            QLabel {
                color: #FFFFFF;
                background: transparent;
                border: none;
                font-family: "Segoe UI";
                font-size: 17px;
                font-weight: 700;
            }
            """
        )

        # Title
        title_label = QLabel(title, self)
        title_label.setGeometry(62, 8, 245, 22)
        title_label.setStyleSheet(
            """
            QLabel {
                color: #1F2937;
                background: transparent;
                border: none;
                font-family: "Segoe UI";
                font-size: 12px;
                font-weight: 700;
            }
            """
        )

        # Message
        message_label = QLabel(message, self)
        message_label.setGeometry(62, 32, 260, 35)
        message_label.setWordWrap(True)
        message_label.setStyleSheet(
            """
            QLabel {
                color: #6B7280;
                background: transparent;
                border: none;
                font-family: "Segoe UI";
                font-size: 11px;
            }
            """
        )

        # Close button
        close_button = QPushButton("×", self)
        close_button.setGeometry(326, 6, 25, 25)
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.setStyleSheet(
            """
            QPushButton {
                color: #9CA3AF;
                background: transparent;
                border: none;
                font-family: "Segoe UI";
                font-size: 18px;
                font-weight: 400;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #F3F4F6;
            }
            """
        )
        close_button.clicked.connect(self.close)

        # Bottom progress line
        progress = QFrame(self)
        progress.setGeometry(0, 73, 360, 3)
        progress.setStyleSheet(
            f"""
            QFrame {{
                background-color: {border_color};
                border: none;
                border-radius: 0px;
            }}
            """
        )

        self.show()
        self.raise_()

        QTimer.singleShot(duration, self.close)


class LoginPage(QWidget):
    """PyQt6 version of the original CustomTkinter LoginPage."""

    login_success_signal = pyqtSignal(object)

    def __init__(self, master=None, login_success=None):
        super().__init__(master)

        self.login_success = login_success
        self.show_password = False
        self._toast = None

        self.base_path = Path(__file__).resolve().parent
        self.image_path = self.base_path / "assets" / "LOGIN.png"

        self.original_pixmap = QPixmap(str(self.image_path))

        if self.original_pixmap.isNull():
            raise FileNotFoundError(
                f"Unable to load login background image:\n{self.image_path}"
            )

        self.setMinimumSize(900, 600)
        self.setStyleSheet("background-color: #EEF1FA;")

        self.create_login_ui()

        # Signal can also be used when LoginPage is used without a callback.
        self.login_success_signal.connect(self._emit_login_success)

        QTimer.singleShot(100, self.resize_background)

    # =========================================================
    # ICONS
    # =========================================================

    def create_icon(self, name):
        """
        Uses standard Unicode symbols so no Tkinter/CustomTkinter
        or ctkfontawesome dependency is required.
        """
        icons = {
            "lock": "🔒",
            "user": "👤",
            "eye": "◉",
            "eye-slash": "◉",
            "right-to-bracket": "→",
        }
        return icons.get(name, "")

    def create_icon_label(self, text, color="#94A3B8", size=16):
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedSize(24, 24)
        label.setStyleSheet(
            f"""
            QLabel {{
                color: {color};
                background: transparent;
                border: none;
                font-family: "Segoe UI";
                font-size: {size}px;
            }}
            """
        )
        return label

    # =========================================================
    # CREATE LOGIN UI
    # =========================================================

    def create_login_ui(self):

        # -----------------------------------------------------
        # TOP LOCK ICON
        # -----------------------------------------------------

        self.lock_circle = QFrame(self)
        self.lock_circle.setFixedSize(48, 48)
        self.lock_circle.setStyleSheet(
            """
            QFrame {
                background-color: #F4F7FF;
                border: 1px solid #2455D6;
                border-radius: 24px;
            }
            """
        )

        lock_layout = QVBoxLayout(self.lock_circle)
        lock_layout.setContentsMargins(0, 0, 0, 0)

        lock_icon = QLabel(self.create_icon("lock"))
        lock_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lock_icon.setStyleSheet(
            """
            QLabel {
                color: #2455D6;
                background: transparent;
                border: none;
                font-size: 21px;
            }
            """
        )
        lock_layout.addWidget(lock_icon)

        # -----------------------------------------------------
        # TITLE
        # -----------------------------------------------------

        self.title_label = QLabel("Login", self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(
            """
            QLabel {
                color: #101828;
                background: transparent;
                border: none;
                font-family: "Segoe UI";
                font-size: 25px;
                font-weight: 700;
            }
            """
        )

        # -----------------------------------------------------
        # SUBTITLE
        # -----------------------------------------------------

        self.subtitle_label = QLabel(
            "Enter your credentials to continue",
            self,
        )
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setStyleSheet(
            """
            QLabel {
                color: #7B8AA5;
                background: transparent;
                border: none;
                font-family: "Segoe UI";
                font-size: 15px;
            }
            """
        )

        # -----------------------------------------------------
        # USERNAME LABEL
        # -----------------------------------------------------

        self.username_label = QLabel("Username", self)
        self.username_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.username_label.setStyleSheet(
            """
            QLabel {
                color: #101828;
                background: transparent;
                border: none;
                font-family: "Segoe UI";
                font-size: 14px;
                font-weight: 700;
            }
            """
        )

        # -----------------------------------------------------
        # USERNAME FIELD
        # -----------------------------------------------------

        self.username_field = QFrame(self)
        self.username_field.setStyleSheet(
            """
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
            }
            """
        )

        username_layout = QHBoxLayout(self.username_field)
        username_layout.setContentsMargins(8, 1, 8, 1)
        username_layout.setSpacing(5)

        username_icon = self.create_icon_label(
            self.create_icon("user"),
            "#94A3B8",
            15,
        )
        username_layout.addWidget(username_icon)

        self.username_entry = QLineEdit(self.username_field)
        self.username_entry.setPlaceholderText("Enter username")
        self.username_entry.setFixedHeight(42)
        self.username_entry.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.username_entry.setStyleSheet(
            """
            QLineEdit {
                background: transparent;
                border: none;
                outline: none;
                color: #101828;
                font-family: "Segoe UI";
                font-size: 13px;
                padding: 0px;
            }
            QLineEdit:focus {
                border: none;
            }
            """
        )
        username_layout.addWidget(self.username_entry)

        # -----------------------------------------------------
        # PASSWORD LABEL
        # -----------------------------------------------------

        self.password_label = QLabel("Password", self)
        self.password_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.password_label.setStyleSheet(
            """
            QLabel {
                color: #101828;
                background: transparent;
                border: none;
                font-family: "Segoe UI";
                font-size: 14px;
                font-weight: 700;
            }
            """
        )

        # -----------------------------------------------------
        # PASSWORD FIELD
        # -----------------------------------------------------

        self.password_field = QFrame(self)
        self.password_field.setStyleSheet(
            """
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
            }
            """
        )

        password_layout = QHBoxLayout(self.password_field)
        password_layout.setContentsMargins(8, 1, 7, 1)
        password_layout.setSpacing(5)

        password_icon = self.create_icon_label(
            self.create_icon("lock"),
            "#94A3B8",
            14,
        )
        password_layout.addWidget(password_icon)

        self.password_entry = QLineEdit(self.password_field)
        self.password_entry.setPlaceholderText("Enter password")
        self.password_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_entry.setFixedHeight(42)
        self.password_entry.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.password_entry.setStyleSheet(
            """
            QLineEdit {
                background: transparent;
                border: none;
                outline: none;
                color: #101828;
                font-family: "Segoe UI";
                font-size: 13px;
                padding: 0px;
            }
            QLineEdit:focus {
                border: none;
            }
            """
        )
        password_layout.addWidget(self.password_entry)

        # -----------------------------------------------------
        # SHOW / HIDE PASSWORD
        # -----------------------------------------------------

        self.eye_button = QPushButton(
            self.create_icon("eye"),
            self.password_field,
        )
        self.eye_button.setFixedSize(28, 28)
        self.eye_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.eye_button.setStyleSheet(
            """
            QPushButton {
                color: #94A3B8;
                background: transparent;
                border: none;
                border-radius: 5px;
                font-family: "Segoe UI";
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #E8EDF5;
            }
            """
        )
        password_layout.addWidget(self.eye_button)

        self.eye_button.clicked.connect(self.toggle_password)

        # -----------------------------------------------------
        # LOGIN BUTTON
        # -----------------------------------------------------

        self.login_button = QPushButton(
            f"{self.create_icon('right-to-bracket')}   Login",
            self,
        )
        self.login_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_button.setFixedHeight(42)
        self.login_button.setStyleSheet(
            """
            QPushButton {
                background-color: #2455D6;
                color: #FFFFFF;
                border: none;
                border-radius: 7px;
                font-family: "Segoe UI";
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #1745C0;
            }
            QPushButton:pressed {
                background-color: #123A9F;
            }
            """
        )
        self.login_button.clicked.connect(self.login)

        # -----------------------------------------------------
        # VERSION
        # -----------------------------------------------------

        self.version_label = QLabel("Version:1.0", self)
        self.version_label.setStyleSheet(
            """
            QLabel {
                color: #9AA1AC;
                background: transparent;
                border: none;
                font-family: "Segoe UI";
                font-size: 9px;
            }
            """
        )

        # -----------------------------------------------------
        # BUILD DATE
        # -----------------------------------------------------

        self.build_label = QLabel("Build Date:20-08-2026", self)
        self.build_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.build_label.setStyleSheet(
            """
            QLabel {
                color: #9AA1AC;
                background: transparent;
                border: none;
                font-family: "Segoe UI";
                font-size: 9px;
            }
            """
        )

        # -----------------------------------------------------
        # FOOTER
        # -----------------------------------------------------

        self.footer_label = QLabel(
            "Powered By Ecosoft Solutions/Version 1.0",
            self,
        )
        self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer_label.setStyleSheet(
            """
            QLabel {
                color: #555555;
                background: transparent;
                border: none;
                font-family: "Segoe UI";
                font-size: 10px;
            }
            """
        )

        # -----------------------------------------------------
        # KEYBOARD
        # -----------------------------------------------------

        self.username_entry.returnPressed.connect(
            self.password_entry.setFocus
        )

        self.password_entry.returnPressed.connect(self.login)

    # =========================================================
    # TOGGLE PASSWORD
    # =========================================================

    def toggle_password(self):

        if self.show_password:
            self.password_entry.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_password = False
            self.eye_button.setText(self.create_icon("eye"))
        else:
            self.password_entry.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_password = True
            self.eye_button.setText(self.create_icon("eye-slash"))

    # =========================================================
    # RESPONSIVE UI
    # =========================================================

    def position_ui(self):

        width = self.width()
        height = self.height()

        if width < 100 or height < 100:
            return

        # Same relative login panel position as the original.
        card_x = 0.785

        login_width = int(width * 0.235)
        login_width = max(300, login_width)
        login_width = min(420, login_width)

        # -----------------------------------------------------
        # TOP LOCK
        # -----------------------------------------------------

        self.lock_circle.move(
            int(width * card_x - self.lock_circle.width() / 2),
            int(height * 0.205 - self.lock_circle.height() / 2),
        )

        # -----------------------------------------------------
        # TITLE
        # -----------------------------------------------------

        title_width = max(login_width, 300)
        self.title_label.setGeometry(
            int(width * card_x - title_width / 2),
            int(height * 0.270 - 20),
            title_width,
            40,
        )

        # -----------------------------------------------------
        # SUBTITLE
        # -----------------------------------------------------

        self.subtitle_label.setGeometry(
            int(width * card_x - title_width / 2),
            int(height * 0.325 - 15),
            title_width,
            30,
        )

        # -----------------------------------------------------
        # USERNAME LABEL
        # -----------------------------------------------------

        label_left = int(width * 0.671)

        self.username_label.setGeometry(
            label_left,
            int(height * 0.380 - 12),
            login_width,
            25,
        )

        # -----------------------------------------------------
        # USERNAME FIELD
        # -----------------------------------------------------

        self.username_field.setGeometry(
            int(width * card_x - login_width / 2),
            int(height * 0.427 - 23),
            login_width,
            46,
        )

        # -----------------------------------------------------
        # PASSWORD LABEL
        # -----------------------------------------------------

        self.password_label.setGeometry(
            label_left,
            int(height * 0.501 - 12),
            login_width,
            25,
        )

        # -----------------------------------------------------
        # PASSWORD FIELD
        # -----------------------------------------------------

        self.password_field.setGeometry(
            int(width * card_x - login_width / 2),
            int(height * 0.548 - 23),
            login_width,
            46,
        )

        # -----------------------------------------------------
        # LOGIN BUTTON
        # -----------------------------------------------------

        self.login_button.setGeometry(
            int(width * card_x - login_width / 2),
            int(height * 0.647 - 21),
            login_width,
            42,
        )

        # -----------------------------------------------------
        # VERSION
        # -----------------------------------------------------

        self.version_label.setGeometry(
            int(width * 0.672),
            int(height * 0.700 - 10),
            max(100, login_width // 2),
            20,
        )

        # -----------------------------------------------------
        # BUILD DATE
        # -----------------------------------------------------

        self.build_label.setGeometry(
            int(width * 0.878 - max(100, login_width // 2)),
            int(height * 0.700 - 10),
            max(100, login_width // 2),
            20,
        )

        # -----------------------------------------------------
        # FOOTER
        # -----------------------------------------------------

        footer_width = max(login_width, 300)
        self.footer_label.setGeometry(
            int(width * card_x - footer_width / 2),
            int(height * 0.773 - 10),
            footer_width,
            25,
        )

        # Keep widgets above the background.
        for widget in (
            self.lock_circle,
            self.title_label,
            self.subtitle_label,
            self.username_label,
            self.username_field,
            self.password_label,
            self.password_field,
            self.login_button,
            self.version_label,
            self.build_label,
            self.footer_label,
        ):
            widget.raise_()

        if self._toast is not None:
            self._toast.raise_()

    # =========================================================
    # BACKGROUND RESIZE
    # =========================================================

    def resize_background(self, event=None):

        width = self.width()
        height = self.height()

        if width < 100 or height < 100:
            return

        # Match the original behavior: stretch LOGIN.png to
        # exactly fill the whole LoginPage.
        resized = self.original_pixmap.scaled(
            width,
            height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        # A QLabel is used only for displaying the image.
        if not hasattr(self, "background"):
            self.background = QLabel(self)
            self.background.setGeometry(0, 0, width, height)
            self.background.setScaledContents(True)
            self.background.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                True,
            )

        self.background.setPixmap(resized)
        self.background.setGeometry(0, 0, width, height)
        self.background.lower()

        self.position_ui()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_background(event)

    # =========================================================
    # TOAST MESSAGE
    # =========================================================

    def show_toast(
        self,
        message,
        message_type="success",
        duration=2500,
    ):
        """
        Shows a small toast message on the top-right of the
        application window.
        """

        if self._toast is not None:
            try:
                self._toast.close()
                self._toast.deleteLater()
            except RuntimeError:
                pass

            self._toast = None

        root = self.window()

        toast = Toast(
            root,
            message,
            message_type,
            duration,
        )

        margin_right = 15
        margin_top = 20

        toast.move(
            root.width() - toast.width() - margin_right,
            margin_top,
        )

        toast.raise_()
        toast.show()

        self._toast = toast

        def clear_reference():
            if self._toast is toast:
                self._toast = None

        QTimer.singleShot(duration + 100, clear_reference)

        return toast

    # =========================================================
    # LOGIN
    # =========================================================

    def login(self):

        username = self.username_entry.text().strip()
        password = self.password_entry.text()

        # -----------------------------------------------------
        # VALIDATION
        # -----------------------------------------------------

        if not username:
            self.show_toast(
                "Please enter username.",
                "warning",
            )
            self.username_entry.setFocus()
            return

        if not password:
            self.show_toast(
                "Please enter password.",
                "warning",
            )
            self.password_entry.setFocus()
            return

        connection = None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    UserId,
                    Username,
                    PasswordHash,
                    Role,
                    ISNULL(DepartmentName, '') AS DepartmentName
                FROM dbo.Users
                WHERE Username = ?
                  AND IsActive = 1
                """,
                username,
            )

            user = cursor.fetchone()

            # -------------------------------------------------
            # INVALID USERNAME
            # -------------------------------------------------

            if not user:
                self.show_toast(
                    "Invalid username or password.",
                    "error",
                )

                self.password_entry.clear()
                self.password_entry.setFocus()
                return

            # -------------------------------------------------
            # PASSWORD CHECK
            # -------------------------------------------------

            stored_hash = user.PasswordHash

            try:
                if isinstance(stored_hash, bytes):
                    hash_bytes = stored_hash
                else:
                    hash_bytes = str(stored_hash).encode("utf-8")

                valid_password = bcrypt.checkpw(
                    password.encode("utf-8"),
                    hash_bytes,
                )

            except (
                ValueError,
                AttributeError,
                TypeError,
            ):
                valid_password = False

            if not valid_password:

                self.show_toast(
                    "Invalid username or password.",
                    "error",
                )

                self.password_entry.clear()
                self.password_entry.setFocus()
                return

            # -------------------------------------------------
            # LOGIN SUCCESS
            # -------------------------------------------------

            self.show_toast(
                f"Welcome {user.Username}! Login successful.",
                "success",
                duration=1800,
            )

            # Keep the same behavior as the original:
            # show success toast briefly, then open Dashboard.
            QTimer.singleShot(
                700,
                lambda: self.login_success_signal.emit(user),
            )

        except Exception as error:

            print("Login error:", error)

            self.show_toast(
                f"Unable to login: {error}",
                "error",
                duration=5000,
            )

        finally:

            if connection:
                try:
                    connection.close()
                except Exception:
                    pass

    # =========================================================
    # LOGIN SUCCESS CALLBACK
    # =========================================================

    def _emit_login_success(self, user):

        if callable(self.login_success):
            self.login_success(user)


# =============================================================
# OPTIONAL STANDALONE TEST
# =============================================================
#
# Your existing main application can create the page like:
#
#     login_page = LoginPage(main_window, login_success)
#     main_window.setCentralWidget(login_page)
#
# If you want to test only this file, run it directly.
# =============================================================

if __name__ == "__main__":

    import sys

    app = QApplication(sys.argv)

    app.setStyle("Fusion")

    window = QWidget()
    window.setWindowTitle("Login")
    window.resize(1366, 768)

    def login_success(user):
        print("LOGIN SUCCESS")
        print("User:", user.Username)
        print("Role:", user.Role)
        print("Department:", user.DepartmentName)

    login_page = LoginPage(
        window,
        login_success=login_success,
    )

    layout = QVBoxLayout(window)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(login_page)

    window.show()

    sys.exit(app.exec())
