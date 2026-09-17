from pathlib import Path

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
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
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

        # The exact dbo.MailSettings.Id currently loaded/edited.
        # None means there is no existing configuration yet.
        self.mail_settings_id = None

        self.setStyleSheet(
            f"""
            QWidget {{
                font-family: "Segoe UI";
                color: {self.TEXT_DARK};
            }}
            """
        )

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
        header.setStyleSheet(
            """
            QFrame {
                background: #FFFFFF;
                border: none;
            }
            """
        )

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
        back_button.setStyleSheet(
            """
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
            """
        )
        back_button.clicked.connect(self.go_back)

        header_layout.addWidget(back_button)
        root.addWidget(header)

        # -----------------------------------------------------
        # BACKGROUND
        # -----------------------------------------------------

        background = QFrame()
        background.setStyleSheet(
            f"""
            QFrame {{
                background: {self.BG_COLOR};
                border: none;
            }}
            """
        )

        background_layout = QVBoxLayout(background)
        background_layout.setContentsMargins(32, 24, 32, 24)

        # -----------------------------------------------------
        # MAIN CARD
        # -----------------------------------------------------

        card = QFrame()
        card.setStyleSheet(
            f"""
            QFrame {{
                background: {self.CARD_COLOR};
                border-radius: 8px;
                border: none;
            }}
            """
        )

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(25, 20, 25, 20)
        card_layout.setSpacing(10)

        title = QLabel("Mail Master")
        title.setStyleSheet(
            """
            QLabel {
                color: #10182D;
                background: transparent;
                font-size: 28px;
                font-weight: bold;
            }
            """
        )
        card_layout.addWidget(title)

        description = QLabel(
            "Configure the mail server and OTP email settings."
        )
        description.setStyleSheet(
            """
            QLabel {
                color: #5F6B80;
                background: transparent;
                font-size: 13px;
            }
            """
        )
        card_layout.addWidget(description)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(
            "background: #6C8FEF; border: none;"
        )
        card_layout.addWidget(line)

        # -----------------------------------------------------
        # FIELDS
        # -----------------------------------------------------

        form = QVBoxLayout()
        form.setSpacing(8)

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
        self.email_password.setEchoMode(
            QLineEdit.EchoMode.Password
        )
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
        clear_button.setStyleSheet(
            """
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
            """
        )
        clear_button.clicked.connect(self.clear_fields)

        self.save_button = QPushButton("Save")
        self.save_button.setFixedSize(90, 36)
        self.save_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.save_button.setStyleSheet(
            """
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

            QPushButton:disabled {
                background: #AFC3F4;
                color: white;
            }
            """
        )
        self.save_button.clicked.connect(self.save_settings)

        buttons.addWidget(clear_button)
        buttons.addSpacing(8)
        buttons.addWidget(self.save_button)

        card_layout.addLayout(buttons)

        # -----------------------------------------------------
        # MAIL SETTINGS TABLE
        # -----------------------------------------------------

        table_title = QLabel("Mail Settings")
        table_title.setStyleSheet(
            """
            QLabel {
                color: #10182D;
                background: transparent;
                font-size: 15px;
                font-weight: 700;
                margin-top: 4px;
            }
            """
        )
        card_layout.addWidget(table_title)

        self.settings_table = QTableWidget()
        self.settings_table.setColumnCount(8)

        self.settings_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Mail Server",
                "Mail Port",
                "Email ID",
                "Password",
                "OTP Subject",
                "OTP Sender",
                "Status",
            ]
        )

        self.settings_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        self.settings_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )

        self.settings_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        self.settings_table.setAlternatingRowColors(True)
        self.settings_table.setMinimumHeight(130)
        self.settings_table.setMaximumHeight(210)
        self.settings_table.verticalHeader().setVisible(False)

        header = self.settings_table.horizontalHeader()
        header.setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        self.settings_table.setStyleSheet(
            """
            QTableWidget {
                background: #FFFFFF;
                alternate-background-color: #F7F9FD;
                color: #25324A;
                border: 1px solid #D5DBE7;
                border-radius: 5px;
                gridline-color: #E2E7F0;
                font-size: 10px;
            }

            QTableWidget::item {
                padding: 4px;
            }

            QTableWidget::item:selected {
                background: #DCE7FF;
                color: #10182D;
            }

            QHeaderView::section {
                background: #EEF3FF;
                color: #25324A;
                border: none;
                border-bottom: 1px solid #D5DBE7;
                padding: 5px;
                font-size: 10px;
                font-weight: 700;
            }
            """
        )

        self.settings_table.itemSelectionChanged.connect(
            self.on_table_row_selected
        )

        card_layout.addWidget(self.settings_table)

        background_layout.addWidget(card)
        background_layout.addStretch()

        root.addWidget(background, 1)

        # -----------------------------------------------------
        # FOOTER
        # -----------------------------------------------------

        footer = QLabel(
            "© 2025 HSI Automation Portal. All rights reserved."
        )
        footer.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        footer.setFixedHeight(25)
        footer.setStyleSheet(
            f"""
            QLabel {{
                color: {self.TEXT_GREY};
                background: {self.BG_COLOR};
                font-size: 9px;
            }}
            """
        )

        root.addWidget(footer)

    # =========================================================
    # FORM ROW
    # =========================================================

    def create_row(self, label_text, edit):
        row = QHBoxLayout()
        row.setSpacing(12)

        label = QLabel(label_text)
        label.setFixedWidth(110)
        label.setStyleSheet(
            """
            QLabel {
                color: #25324A;
                font-size: 11px;
                font-weight: 600;
                background: transparent;
            }
            """
        )

        edit.setMinimumHeight(36)
        edit.setStyleSheet(
            """
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
            """
        )

        row.addWidget(label)
        row.addWidget(edit, 1)

        return row

    # =========================================================
    # LOAD ALL SETTINGS
    # =========================================================

    def load_settings(self):
        """
        Load every row from dbo.MailSettings into the table.

        The newest active row is automatically selected and loaded
        into the form. Its Id is stored for Update.
        """

        connection = None
        cursor = None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    Id,
                    MailServer,
                    MailPort,
                    EmailId,
                    EmailPassword,
                    OtpSubject,
                    OtpSender,
                    IsActive
                FROM dbo.MailSettings
                ORDER BY Id DESC
                """
            )

            rows = cursor.fetchall()

            self.settings_table.setRowCount(0)

            active_row_index = None

            for row_index, row in enumerate(rows):
                self.settings_table.insertRow(row_index)

                display_values = [
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    "********",
                    row[5],
                    row[6],
                    "Active" if row[7] else "Inactive",
                ]

                for column_index, value in enumerate(
                    display_values
                ):
                    item = QTableWidgetItem(
                        str(value if value is not None else "")
                    )

                    if column_index == 0:
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignCenter
                        )

                    self.settings_table.setItem(
                        row_index,
                        column_index,
                        item,
                    )

                # Select the newest active row.
                if row[7] and active_row_index is None:
                    active_row_index = row_index

            if active_row_index is not None:
                self.settings_table.selectRow(
                    active_row_index
                )

            elif rows:
                # If there is no active row, load newest row.
                self.settings_table.selectRow(0)

            else:
                # First-time configuration.
                self.mail_settings_id = None
                self.save_button.setText("Save")

        except Exception as error:
            print(
                "Mail Master load error:",
                repr(error),
            )

            QMessageBox.critical(
                self,
                "Database Error",
                f"Failed to load mail settings.\n\n{error}",
            )

        finally:
            self.close_database(
                cursor,
                connection,
            )

    # =========================================================
    # TABLE ROW SELECTED
    # =========================================================

    def on_table_row_selected(self):
        """
        Get the Id from the selected table row and load only
        that database record into the form.
        """

        selected_rows = (
            self.settings_table
            .selectionModel()
            .selectedRows()
        )

        if not selected_rows:
            return

        row_index = selected_rows[0].row()

        id_item = self.settings_table.item(
            row_index,
            0,
        )

        if id_item is None:
            return

        try:
            settings_id = int(
                id_item.text().strip()
            )
        except (TypeError, ValueError):
            return

        self.load_settings_by_id(settings_id)

    # =========================================================
    # LOAD EXACT ROW
    # =========================================================

    def load_settings_by_id(self, settings_id):
        connection = None
        cursor = None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    Id,
                    MailServer,
                    MailPort,
                    EmailId,
                    EmailPassword,
                    OtpSubject,
                    OtpSender
                FROM dbo.MailSettings
                WHERE Id = ?
                """,
                settings_id,
            )

            row = cursor.fetchone()

            if not row:
                return

            # This is the critical value used by UPDATE.
            self.mail_settings_id = int(row[0])

            self.mail_server.setText(
                str(row[1] or "")
            )

            self.mail_port.setText(
                str(row[2] or "")
            )

            self.email_id.setText(
                str(row[3] or "")
            )

            self.email_password.setText(
                str(row[4] or "")
            )

            self.otp_subject.setText(
                str(row[5] or "")
            )

            self.otp_sender.setText(
                str(row[6] or "")
            )

            # Existing database row.
            self.save_button.setText("Update")

        except Exception as error:
            print(
                "Mail Master row load error:",
                repr(error),
            )

            QMessageBox.critical(
                self,
                "Database Error",
                f"Failed to load selected mail settings.\n\n{error}",
            )

        finally:
            self.close_database(
                cursor,
                connection,
            )

    # =========================================================
    # SAVE / UPDATE
    # =========================================================

    def save_settings(self):
        """
        If mail_settings_id is None:
            INSERT one row.

        If mail_settings_id exists:
            UPDATE ONLY that Id.

        No other row is changed and Update never performs INSERT.
        """

        server = self.mail_server.text().strip()
        port = self.mail_port.text().strip()
        email_id = self.email_id.text().strip()
        password = self.email_password.text()
        subject = self.otp_subject.text().strip()
        sender = self.otp_sender.text().strip()

        # -----------------------------------------------------
        # VALIDATION
        # -----------------------------------------------------

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

        if port_number < 1 or port_number > 65535:
            QMessageBox.warning(
                self,
                "Validation",
                "Mail Port must be between 1 and 65535.",
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

        if not subject:
            QMessageBox.warning(
                self,
                "Validation",
                "Please enter OTP Subject.",
            )
            return

        if not sender:
            QMessageBox.warning(
                self,
                "Validation",
                "Please enter OTP Sender.",
            )
            return

        connection = None
        cursor = None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            # =================================================
            # EXISTING ROW -> UPDATE ONLY THIS ID
            # =================================================

            if self.mail_settings_id is not None:

                settings_id = self.mail_settings_id

                cursor.execute(
                    """
                    UPDATE dbo.MailSettings
                    SET
                        MailServer = ?,
                        MailPort = ?,
                        EmailId = ?,
                        EmailPassword = ?,
                        OtpSubject = ?,
                        OtpSender = ?,
                        ModifiedOn = GETDATE(),
                        ModifiedBy = ?
                    WHERE Id = ?
                    """,
                    (
                        server,
                        port_number,
                        email_id,
                        password,
                        subject,
                        sender,
                        "Admin",
                        settings_id,
                    ),
                )

                if cursor.rowcount == 0:
                    raise Exception(
                        f"MailSettings row Id {settings_id} "
                        "was not found. No new row was inserted."
                    )

                connection.commit()

                QMessageBox.information(
                    self,
                    "Mail Master",
                    "Mail settings updated successfully.\n\n"
                    f"Updated Row ID: {settings_id}",
                )

            # =================================================
            # FIRST-TIME CONFIGURATION -> INSERT ONE ROW
            # =================================================

            else:

                cursor.execute(
                    """
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
                    OUTPUT INSERTED.Id
                    VALUES
                    (
                        ?, ?, ?, ?, ?, ?, 1, ?, GETDATE()
                    )
                    """,
                    (
                        server,
                        port_number,
                        email_id,
                        password,
                        subject,
                        sender,
                        "Admin",
                    ),
                )

                inserted_row = cursor.fetchone()

                if not inserted_row:
                    raise Exception(
                        "Mail settings could not be inserted."
                    )

                self.mail_settings_id = int(
                    inserted_row[0]
                )

                connection.commit()

                QMessageBox.information(
                    self,
                    "Mail Master",
                    "Mail settings saved successfully.\n\n"
                    f"Created Row ID: {self.mail_settings_id}",
                )

            # Refresh table from DB.
            self.load_settings()

            # Keep the same record selected after refresh.
            self.select_table_row_by_id(
                self.mail_settings_id
            )

            self.save_button.setText("Update")

        except Exception as error:

            if connection:
                try:
                    connection.rollback()
                except Exception:
                    pass

            print(
                "Mail Master save/update error:",
                repr(error),
            )

            QMessageBox.critical(
                self,
                "Database Error",
                f"Failed to save mail settings.\n\n{error}",
            )

        finally:
            self.close_database(
                cursor,
                connection,
            )

    # =========================================================
    # SELECT TABLE ROW BY ID
    # =========================================================

    def select_table_row_by_id(self, settings_id):
        if settings_id is None:
            return

        for row_index in range(
            self.settings_table.rowCount()
        ):
            id_item = self.settings_table.item(
                row_index,
                0,
            )

            if (
                id_item is not None
                and id_item.text().strip()
                == str(settings_id)
            ):
                self.settings_table.selectRow(
                    row_index
                )
                return

    # =========================================================
    # CLEAR
    # =========================================================

    def clear_fields(self):
        """
        Clear the form and start a new first-time configuration.

        No database change occurs until Save is clicked.
        """

        self.mail_settings_id = None

        self.mail_server.clear()
        self.mail_port.setText("995")
        self.email_id.clear()
        self.email_password.clear()
        self.otp_subject.clear()
        self.otp_sender.clear()

        self.settings_table.clearSelection()

        self.save_button.setText("Save")

    # =========================================================
    # DATABASE CLEANUP
    # =========================================================

    @staticmethod
    def close_database(cursor, connection):
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
    # BACK
    # =========================================================

    def go_back(self):
        if callable(self.back_callback):
            self.back_callback()


# =============================================================
# STANDALONE TEST
# =============================================================

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = QMainWindow()
    window.setWindowTitle(
        "HSI Automation Portal - Mail Master"
    )
    window.resize(1347, 758)
    window.setMinimumSize(1100, 620)

    page = MailMasterPage(
        window,
        back_callback=window.close,
    )

    window.setCentralWidget(page)
    window.show()

    sys.exit(app.exec())
