from pathlib import Path
import poplib

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database import get_connection


class MailMasterPage(QWidget):

    BG_COLOR = "#EEF1FA"
    CARD_COLOR = "#E4E9F7"
    PRIMARY = "#1457E6"
    TEXT_DARK = "#10182D"
    TEXT_GREY = "#71809E"

    def __init__(self, master=None, back_callback=None):
        super().__init__(master)

        self.back_callback = back_callback
        self.base_path = Path(__file__).resolve().parent

        self.setStyleSheet(f"""
            QWidget {{
                font-family: "Segoe UI";
                color: {self.TEXT_DARK};
            }}
        """)

        self.create_ui()
        self.load_settings()

    # =========================================================
    # UI
    # =========================================================

    def create_ui(self):

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -----------------------------------------------------
        # HEADER
        # -----------------------------------------------------

        header = QFrame()
        header.setFixedHeight(70)
        header.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: none;
            }
        """)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)

        logo = QLabel()
        logo.setFixedSize(145, 48)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo_paths = [
            self.base_path / "assets" / "HSI_LOGO.png",
            self.base_path / "assets" / "HSI.png",
            self.base_path / "assets" / "Dashtoplogo.png",
        ]

        logo_path = next(
            (path for path in logo_paths if path.exists()),
            None,
        )

        if logo_path:
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                logo.setPixmap(
                    pixmap.scaled(
                        145,
                        48,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        else:
            logo.setText("HSI\nAUTOMATION PORTAL")

        header_layout.addWidget(logo)
        header_layout.addStretch()

        back_button = QPushButton("←")
        back_button.setFixedSize(40, 40)
        back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        back_button.setToolTip("Back")
        back_button.setStyleSheet("""
            QPushButton {
                background: #2E6DEB;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #174FC5;
            }
        """)
        back_button.clicked.connect(self.go_back)

        header_layout.addWidget(back_button)
        root.addWidget(header)

        # -----------------------------------------------------
        # BACKGROUND
        # -----------------------------------------------------

        background = QFrame()
        background.setStyleSheet(f"""
            QFrame {{
                background: {self.BG_COLOR};
                border: none;
            }}
        """)

        background_layout = QVBoxLayout(background)
        background_layout.setContentsMargins(40, 28, 40, 28)

        # -----------------------------------------------------
        # MAIN CARD
        # -----------------------------------------------------

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {self.CARD_COLOR};
                border-radius: 8px;
                border: none;
            }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(25, 20, 25, 20)
        card_layout.setSpacing(12)

        title = QLabel("Mail Master")
        title.setStyleSheet("""
            QLabel {
                color: #10182D;
                background: transparent;
                font-size: 28px;
                font-weight: bold;
            }
        """)
        card_layout.addWidget(title)

        description = QLabel(
            "Configure the mail server and OTP email settings."
        )
        description.setStyleSheet("""
            QLabel {
                color: #5F6B80;
                background: transparent;
                font-size: 13px;
            }
        """)
        card_layout.addWidget(description)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background: #6C8FEF; border: none;")
        card_layout.addWidget(line)

        # -----------------------------------------------------
        # FIELDS
        # -----------------------------------------------------

        form = QVBoxLayout()
        form.setSpacing(10)

        self.mail_server = QLineEdit()
        self.mail_server.setPlaceholderText("Enter mail server")
        form.addLayout(
            self.create_row(
                "Mail Server",
                self.mail_server,
            )
        )

        self.mail_port = QLineEdit()
        self.mail_port.setPlaceholderText("995")
        form.addLayout(
            self.create_row(
                "Mail Port",
                self.mail_port,
            )
        )

        self.email_id = QLineEdit()
        self.email_id.setPlaceholderText("Enter email ID")
        form.addLayout(
            self.create_row(
                "Email ID",
                self.email_id,
            )
        )

        self.email_password = QLineEdit()
        self.email_password.setPlaceholderText("Enter email password")
        self.email_password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addLayout(
            self.create_row(
                "Password",
                self.email_password,
            )
        )

        self.otp_subject = QLineEdit()
        self.otp_subject.setPlaceholderText("MSetu Logon OTP")
        form.addLayout(
            self.create_row(
                "OTP Subject",
                self.otp_subject,
            )
        )

        self.otp_sender = QLineEdit()
        self.otp_sender.setPlaceholderText("OTP sender email")
        form.addLayout(
            self.create_row(
                "OTP Sender",
                self.otp_sender,
            )
        )

        card_layout.addLayout(form)

        # -----------------------------------------------------
        # BUTTONS
        # -----------------------------------------------------

        buttons = QHBoxLayout()
        buttons.addStretch()

        clear_button = QPushButton("Clear")
        clear_button.setFixedSize(90, 36)
        clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_button.setStyleSheet("""
            QPushButton {
                background: white;
                color: #374151;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #E5E7EB;
            }
        """)
        clear_button.clicked.connect(self.clear_fields)

        test_button = QPushButton("Test Connection")
        test_button.setFixedSize(125, 36)
        test_button.setCursor(Qt.CursorShape.PointingHandCursor)
        test_button.setStyleSheet("""
            QPushButton {
                background: #FFFFFF;
                color: #1457E6;
                border: 1px solid #1457E6;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #EEF5FF;
            }
        """)
        test_button.clicked.connect(self.test_connection)

        save_button = QPushButton("Save")
        save_button.setFixedSize(90, 36)
        save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        save_button.setStyleSheet("""
            QPushButton {
                background: #1457E6;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #0E48C7;
            }
        """)
        save_button.clicked.connect(self.save_settings)

        buttons.addWidget(clear_button)
        buttons.addSpacing(8)
        buttons.addWidget(test_button)
        buttons.addSpacing(8)
        buttons.addWidget(save_button)

        card_layout.addLayout(buttons)

        background_layout.addWidget(card)
        background_layout.addStretch()

        root.addWidget(background, 1)

        # -----------------------------------------------------
        # FOOTER
        # -----------------------------------------------------

        footer = QLabel(
            "© 2025 HSI Automation Portal. All rights reserved."
        )
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setFixedHeight(25)
        footer.setStyleSheet(f"""
            QLabel {{
                color: {self.TEXT_GREY};
                background: {self.BG_COLOR};
                font-size: 9px;
            }}
        """)

        root.addWidget(footer)

    # =========================================================
    # FORM ROW
    # =========================================================

    def create_row(self, label_text, edit):

        row = QHBoxLayout()
        row.setSpacing(12)

        label = QLabel(label_text)
        label.setFixedWidth(110)
        label.setStyleSheet("""
            QLabel {
                color: #25324A;
                font-size: 11px;
                font-weight: 600;
                background: transparent;
            }
        """)

        edit.setMinimumHeight(36)
        edit.setStyleSheet("""
            QLineEdit {
                background: #FFFFFF;
                color: #25324A;
                border: 1px solid #D5DBE7;
                border-radius: 5px;
                padding: 0 10px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 1px solid #4D7DF0;
            }
        """)

        row.addWidget(label)
        row.addWidget(edit, 1)

        return row

    # =========================================================
    # LOAD
    # =========================================================

    def load_settings(self):

        connection = None
        cursor = None

        try:

            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute("""
                SELECT TOP 1
                    MailServer,
                    MailPort,
                    EmailId,
                    EmailPassword,
                    OtpSubject,
                    OtpSender
                FROM dbo.MailSettings
                WHERE IsActive = 1
                ORDER BY Id DESC
            """)

            row = cursor.fetchone()

            if row:

                self.mail_server.setText(
                    str(row[0] or "")
                )

                self.mail_port.setText(
                    str(row[1] or "")
                )

                self.email_id.setText(
                    str(row[2] or "")
                )

                self.email_password.setText(
                    str(row[3] or "")
                )

                self.otp_subject.setText(
                    str(row[4] or "")
                )

                self.otp_sender.setText(
                    str(row[5] or "")
                )

        except Exception as error:

            print(
                "Mail Master load error:",
                error,
            )

        finally:

            try:
                if cursor:
                    cursor.close()
            except Exception:
                pass

            try:
                if connection:
                    connection.close()
            except Exception:
                pass

    # =========================================================
    # SAVE
    # =========================================================

    def save_settings(self):

        server = self.mail_server.text().strip()
        port = self.mail_port.text().strip()
        email_id = self.email_id.text().strip()
        password = self.email_password.text()
        subject = self.otp_subject.text().strip()
        sender = self.otp_sender.text().strip()

        if not server:
            QMessageBox.warning(
                self,
                "Validation",
                "Please enter Mail Server.",
            )
            return

        try:
            port_number = int(port)
        except ValueError:
            QMessageBox.warning(
                self,
                "Validation",
                "Mail Port must be a number.",
            )
            return

        if not email_id:
            QMessageBox.warning(
                self,
                "Validation",
                "Please enter Email ID.",
            )
            return

        if not password:
            QMessageBox.warning(
                self,
                "Validation",
                "Please enter Email Password.",
            )
            return

        connection = None
        cursor = None

        try:

            connection = get_connection()
            cursor = connection.cursor()

            # Deactivate the previous active configuration.
            cursor.execute("""
                UPDATE dbo.MailSettings
                SET
                    IsActive = 0,
                    ModifiedOn = GETDATE(),
                    ModifiedBy = ?
                WHERE IsActive = 1
            """, "Admin")

            cursor.execute("""
                INSERT INTO dbo.MailSettings
                (
                    MailServer,
                    MailPort,
                    EmailId,
                    EmailPassword,
                    OtpSubject,
                    OtpSender,
                    IsActive,
                    CreatedBy,
                    CreatedOn
                )
                VALUES
                (
                    ?, ?, ?, ?, ?, ?, 1, ?, GETDATE()
                )
            """,
                server,
                port_number,
                email_id,
                password,
                subject,
                sender,
                "Admin",
            )

            connection.commit()

            QMessageBox.information(
                self,
                "Mail Master",
                "Mail settings saved successfully.",
            )

        except Exception as error:

            if connection:
                try:
                    connection.rollback()
                except Exception:
                    pass

            QMessageBox.critical(
                self,
                "Database Error",
                f"Failed to save mail settings.\n\n{error}",
            )

        finally:

            try:
                if cursor:
                    cursor.close()
            except Exception:
                pass

            try:
                if connection:
                    connection.close()
            except Exception:
                pass

    # =========================================================
    # TEST CONNECTION
    # =========================================================

    def test_connection(self):

        server = self.mail_server.text().strip()
        port_text = self.mail_port.text().strip()
        email_id = self.email_id.text().strip()
        password = self.email_password.text()

        if not server or not port_text or not email_id or not password:
            QMessageBox.warning(
                self,
                "Validation",
                "Please fill Mail Server, Port, Email ID and Password.",
            )
            return

        try:

            port = int(port_text)

            QMessageBox.information(
                self,
                "Mail Connection",
                "Connecting to the mail server...\nPlease wait.",
            )

            mail = poplib.POP3_SSL(
                server,
                port,
                timeout=30,
            )

            try:

                mail.user(email_id)
                mail.pass_(password)

                response, messages, octets = mail.list()
                total = len(messages)

            finally:

                mail.quit()

            QMessageBox.information(
                self,
                "Mail Connection",
                f"Mail login successful.\n\n"
                f"Server: {server}\n"
                f"Port: {port}\n"
                f"Emails: {total}",
            )

        except Exception as error:

            QMessageBox.critical(
                self,
                "Mail Connection Failed",
                f"Unable to connect to mail server.\n\n{error}",
            )

    # =========================================================
    # CLEAR
    # =========================================================

    def clear_fields(self):

        self.mail_server.clear()
        self.mail_port.setText("995")
        self.email_id.clear()
        self.email_password.clear()
        self.otp_subject.clear()
        self.otp_sender.clear()

    # =========================================================
    # BACK
    # =========================================================

    def go_back(self):

        if callable(self.back_callback):
            self.back_callback()


if __name__ == "__main__":

    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = QMainWindow()
    window.setWindowTitle("HSI Automation Portal - Mail Master")
    window.resize(1347, 758)
    window.setMinimumSize(1100, 620)

    page = MailMasterPage(
        window,
        back_callback=window.close,
    )

    window.setCentralWidget(page)
    window.show()

    sys.exit(app.exec())
