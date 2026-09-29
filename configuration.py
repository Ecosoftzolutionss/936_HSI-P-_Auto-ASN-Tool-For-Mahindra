import platform

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database import get_connection


class ConfigurationPage(QWidget):
    """
    HSI Mahindra Auto ASN - Configuration.

    Stores:
      1. dbo.SETTINGS
         - SYSTEM_NAME
         - DS_INVOICE_PATH
         - F_PATH
         - ASN_BARCODE_PATH
         - PORTAL_USERID
         - PORTAL_PASSWORD

      2. dbo.MailSettings
         - MailServer
         - MailPort
         - EmailId
         - EmailPassword
         - OtpSubject
         - OtpSender

    First time:
        Save -> INSERT missing configuration rows -> button becomes Update

    Existing configuration:
        Update -> UPDATE the existing rows
    """

    BG_COLOR = "#EEF1FA"
    PRIMARY = "#1457E6"
    TEXT_DARK = "#10182D"
    TEXT_GREY = "#71809E"
    CARD_COLOR = "#E4E9F7"

    def __init__(self, master=None, back_callback=None):
        super().__init__(master)

        self.back_callback = back_callback
        self.system_name = platform.node()

        self.settings_id = None
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

        header = QFrame()
        header.setFixedHeight(70)
        header.setStyleSheet("background:#FFFFFF; border:none;")

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)

        title = QLabel("Configuration")
        title.setStyleSheet(
            """
            QLabel {
                color: #10182D;
                font-size: 18px;
                font-weight: bold;
                background: transparent;
            }
            """
        )

        back = QPushButton("←")
        back.setFixedSize(40, 40)
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.setStyleSheet(
            """
            QPushButton {
                background: #2E6DEB;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton:hover { background: #174FC5; }
            """
        )
        back.clicked.connect(self.go_back)

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(back)
        root.addWidget(header)

        background = QFrame()
        background.setStyleSheet(
            f"background:{self.BG_COLOR}; border:none;"
        )

        bg_layout = QVBoxLayout(background)
        bg_layout.setContentsMargins(28, 20, 28, 20)

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
        card_layout.setContentsMargins(18, 14, 18, 18)
        card_layout.setSpacing(9)

        heading = QLabel("Configuration")
        heading.setStyleSheet(
            """
            QLabel {
                color: #25324A;
                font-size: 22px;
                font-weight: 600;
                background: transparent;
            }
            """
        )
        card_layout.addWidget(heading)

        description = QLabel(
            "Configure file paths, Mahindra portal credentials and OTP mail settings."
        )
        description.setStyleSheet(
            "color:#5F6B80; font-size:12px; background:transparent;"
        )
        card_layout.addWidget(description)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background:#6C8FEF; border:none;")
        card_layout.addWidget(line)

        # -----------------------------------------------------
        # Application configuration
        # -----------------------------------------------------
        section1 = QLabel("Application Settings")
        section1.setStyleSheet(self.section_style())
        card_layout.addWidget(section1)

        form = QVBoxLayout()
        form.setSpacing(8)

        self.invoice_path = QLineEdit()
        self.flatfile_path = QLineEdit()
        self.asn_barcode_path = QLineEdit()
        self.portal_userid = QLineEdit()
        self.portal_password = QLineEdit()

        self.portal_password.setEchoMode(QLineEdit.EchoMode.Password)

        for edit in (
            self.invoice_path,
            self.flatfile_path,
            self.asn_barcode_path,
            self.portal_userid,
            self.portal_password,
        ):
            edit.setMinimumHeight(34)
            edit.setStyleSheet(self.input_style())

        form.addLayout(
            self.path_row("Invoice Path", self.invoice_path, "Select invoice path")
        )
        form.addLayout(
            self.path_row("Flatfile Path", self.flatfile_path, "Select flatfile path")
        )
        form.addLayout(
            self.path_row(
                "ASN Barcode Path",
                self.asn_barcode_path,
                "Select ASN barcode path",
            )
        )
        form.addLayout(self.field_row("Portal User ID", self.portal_userid))
        form.addLayout(self.field_row("Portal Password", self.portal_password))

        card_layout.addLayout(form)

        # Application table has its own Clear / Save(Update) controls.
        app_buttons = QHBoxLayout()
        app_buttons.addStretch()

        self.app_clear_btn = QPushButton("Clear")
        self.app_save_btn = QPushButton("Save")

        self.app_clear_btn.setFixedSize(82, 36)
        self.app_save_btn.setFixedSize(82, 36)

        self.app_clear_btn.setStyleSheet(self.clear_style())
        self.app_save_btn.setStyleSheet(self.save_style())

        self.app_clear_btn.clicked.connect(self.clear_application_fields)
        self.app_save_btn.clicked.connect(self.save_application_settings)

        app_buttons.addWidget(self.app_clear_btn)
        app_buttons.addSpacing(10)
        app_buttons.addWidget(self.app_save_btn)
        card_layout.addLayout(app_buttons)

        # Clear visual separator because Application Settings and
        # MailSettings are stored in different database tables.
        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet(
            "background:#B8C4DD; border:none; margin-top:4px; margin-bottom:4px;"
        )
        card_layout.addWidget(separator)

        # -----------------------------------------------------
        # Mail / OTP configuration
        # -----------------------------------------------------
        section2 = QLabel("Mail / OTP Settings")
        section2.setStyleSheet(self.section_style())
        card_layout.addWidget(section2)

        mail_grid = QGridLayout()
        mail_grid.setHorizontalSpacing(14)
        mail_grid.setVerticalSpacing(8)

        self.mail_server = QLineEdit()
        self.mail_port = QLineEdit()
        self.email_id = QLineEdit()
        self.email_password = QLineEdit()
        self.otp_subject = QLineEdit()
        self.otp_sender = QLineEdit()

        self.mail_port.setPlaceholderText("e.g. 993")
        self.email_id.setPlaceholderText("OTP email address")
        self.email_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.email_password.setPlaceholderText("Email password")
        self.otp_subject.setPlaceholderText("e.g. MSetu Logon OTP")
        self.otp_sender.setPlaceholderText("OTP sender email address")

        mail_edits = (
            self.mail_server,
            self.mail_port,
            self.email_id,
            self.email_password,
            self.otp_subject,
            self.otp_sender,
        )

        for edit in mail_edits:
            edit.setMinimumHeight(34)
            edit.setStyleSheet(self.input_style())

        mail_grid.addWidget(self._mail_label("Mail Server"), 0, 0)
        mail_grid.addWidget(self.mail_server, 0, 1)
        mail_grid.addWidget(self._mail_label("Mail Port"), 0, 2)
        mail_grid.addWidget(self.mail_port, 0, 3)

        mail_grid.addWidget(self._mail_label("Email ID"), 1, 0)
        mail_grid.addWidget(self.email_id, 1, 1)
        mail_grid.addWidget(self._mail_label("Email Password"), 1, 2)
        mail_grid.addWidget(self.email_password, 1, 3)

        mail_grid.addWidget(self._mail_label("OTP Subject"), 2, 0)
        mail_grid.addWidget(self.otp_subject, 2, 1)
        mail_grid.addWidget(self._mail_label("OTP Sender"), 2, 2)
        mail_grid.addWidget(self.otp_sender, 2, 3)

        mail_grid.setColumnStretch(1, 1)
        mail_grid.setColumnStretch(3, 1)

        card_layout.addLayout(mail_grid)

        # MailSettings table has its own Clear / Save(Update) controls.
        mail_buttons = QHBoxLayout()
        mail_buttons.addStretch()

        self.mail_clear_btn = QPushButton("Clear")
        self.mail_save_btn = QPushButton("Save")

        self.mail_clear_btn.setFixedSize(82, 36)
        self.mail_save_btn.setFixedSize(82, 36)

        self.mail_clear_btn.setStyleSheet(self.clear_style())
        self.mail_save_btn.setStyleSheet(self.save_style())

        self.mail_clear_btn.clicked.connect(self.clear_mail_fields)
        self.mail_save_btn.clicked.connect(self.save_mail_settings)

        mail_buttons.addWidget(self.mail_clear_btn)
        mail_buttons.addSpacing(10)
        mail_buttons.addWidget(self.mail_save_btn)
        card_layout.addLayout(mail_buttons)

        bg_layout.addWidget(card)
        bg_layout.addStretch()

        root.addWidget(background, 1)

    # =========================================================
    # Styles / rows
    # =========================================================

    def section_style(self):
        return """
            QLabel {
                color:#25324A;
                background:transparent;
                font-size:13px;
                font-weight:700;
                padding-top:3px;
            }
        """

    def _mail_label(self, text):
        label = QLabel(text)
        label.setStyleSheet(
            "font-size:11px; font-weight:600; color:#25324A; background:transparent;"
        )
        return label

    def input_style(self):
        return """
            QLineEdit {
                background: #FFFFFF;
                color: #25324A;
                border: 1px solid #D5DBE7;
                border-radius: 4px;
                padding: 0 10px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 1px solid #4D7DF0;
            }
        """

    def field_row(self, label_text, edit):
        row = QHBoxLayout()
        row.setSpacing(12)

        label = QLabel(label_text)
        label.setFixedWidth(105)
        label.setStyleSheet(
            "font-size:11px; font-weight:600; color:#25324A;"
        )

        row.addWidget(label)
        row.addWidget(edit, 1)
        return row

    def path_row(self, label_text, edit, placeholder):
        edit.setPlaceholderText(placeholder)

        browse = QPushButton("📁 Browse")
        browse.setFixedSize(90, 34)
        browse.setCursor(Qt.CursorShape.PointingHandCursor)
        browse.setStyleSheet(
            """
            QPushButton {
                background: white;
                color: #25324A;
                border: 1px solid #D5DBE7;
                border-radius: 4px;
                font-size: 9px;
            }
            QPushButton:hover { background:#F5F7FB; }
            """
        )
        browse.clicked.connect(lambda: self.browse_folder(edit))

        row = self.field_row(label_text, edit)
        row.addWidget(browse)
        return row

    def clear_style(self):
        return """
            QPushButton {
                background:#FFFFFF;
                color:#25324A;
                border:1px solid #D6DCE8;
                border-radius:4px;
                font-size:11px;
            }
            QPushButton:hover { background:#F5F7FB; }
        """

    def save_style(self):
        return """
            QPushButton {
                background:#1457E6;
                color:#FFFFFF;
                border:none;
                border-radius:5px;
                font-size:11px;
                font-weight:600;
            }
            QPushButton:hover { background:#0E48C7; }
        """

    # =========================================================
    # Helpers
    # =========================================================

    def browse_folder(self, target):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder",
            target.text().strip() or "",
        )
        if folder:
            target.setText(folder)

    # =========================================================
    # Load
    # =========================================================

    def load_settings(self):
        connection = None
        cursor = None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            # -----------------------------
            # dbo.SETTINGS
            # -----------------------------
            # First try the current Windows computer name.
            # This keeps multi-system installations working.
            cursor.execute(
                """
                SELECT TOP 1
                    ID,
                    SYSTEM_NAME,
                    DS_INVOICE_PATH,
                    F_PATH,
                    ASN_BARCODE_PATH,
                    PORTAL_USERID,
                    PORTAL_PASSWORD
                FROM dbo.SETTINGS
                WHERE LTRIM(RTRIM(SYSTEM_NAME)) = LTRIM(RTRIM(?))
                ORDER BY ID DESC
                """,
                self.system_name,
            )
            settings_row = cursor.fetchone()

            # IMPORTANT: If the database row exists but SYSTEM_NAME is not
            # exactly the same as platform.node(), do not show blank fields.
            # Load the latest SETTINGS row as a safe fallback.
            if not settings_row:
                cursor.execute(
                    """
                    SELECT TOP 1
                        ID,
                        SYSTEM_NAME,
                        DS_INVOICE_PATH,
                        F_PATH,
                        ASN_BARCODE_PATH,
                        PORTAL_USERID,
                        PORTAL_PASSWORD
                    FROM dbo.SETTINGS
                    ORDER BY ID DESC
                    """
                )
                settings_row = cursor.fetchone()

            if settings_row:
                self.settings_id = int(settings_row[0])

                # Use the database system name after loading an existing row.
                # Future updates are done by ID, so the hostname mismatch is
                # no longer a problem.
                self.system_name = str(settings_row[1] or self.system_name).strip()

                self.invoice_path.setText(str(settings_row[2] or ""))
                self.flatfile_path.setText(str(settings_row[3] or ""))
                self.asn_barcode_path.setText(str(settings_row[4] or ""))
                self.portal_userid.setText(str(settings_row[5] or ""))
                self.portal_password.setText(str(settings_row[6] or ""))
                self.app_save_btn.setText("Update")
            else:
                self.settings_id = None
                self.app_save_btn.setText("Save")

            # -----------------------------
            # dbo.MailSettings
            # -----------------------------
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
                WHERE IsActive = 1
                ORDER BY Id DESC
                """
            )
            mail_row = cursor.fetchone()

            # If an old installation has a row but IsActive is not set
            # correctly, still display the latest saved mail configuration.
            if not mail_row:
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
                    ORDER BY Id DESC
                    """
                )
                mail_row = cursor.fetchone()

            if mail_row:
                self.mail_settings_id = int(mail_row[0])
                self.mail_server.setText(str(mail_row[1] or ""))
                self.mail_port.setText(str(mail_row[2] or ""))
                self.email_id.setText(str(mail_row[3] or ""))
                self.email_password.setText(str(mail_row[4] or ""))
                self.otp_subject.setText(str(mail_row[5] or ""))
                self.otp_sender.setText(str(mail_row[6] or ""))
                self.mail_save_btn.setText("Update")
            else:
                self.mail_settings_id = None
                self.mail_save_btn.setText("Save")

        except Exception as error:
            QMessageBox.critical(
                self,
                "Configuration Error",
                f"Unable to load configuration.\n\n{error}",
            )

        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    # =========================================================
    # Message / focus helper
    # =========================================================

    def warn(self, message, widget=None):
        """Show a validation message and focus the invalid field."""
        QMessageBox.warning(self, "Validation", message)
        if widget is not None:
            widget.setFocus()
            if isinstance(widget, QLineEdit):
                widget.selectAll()

    # =========================================================
    # Validation
    # =========================================================

    def validate_application_fields(self):
        fields = (
            (self.invoice_path, "Please enter Invoice Path."),
            (self.flatfile_path, "Please enter Flatfile Path."),
            (self.asn_barcode_path, "Please enter ASN Barcode Path."),
            (self.portal_userid, "Please enter Mahindra Portal User ID."),
            (self.portal_password, "Please enter Mahindra Portal Password."),
        )

        for widget, message in fields:
            if not widget.text().strip():
                self.warn(message, widget)
                return False

        return True

    def validate_mail_fields(self):
        fields = (
            (self.mail_server, "Please enter Mail Server."),
            (self.mail_port, "Please enter Mail Port."),
            (self.email_id, "Please enter Email ID."),
            (self.email_password, "Please enter Email Password."),
            (self.otp_subject, "Please enter OTP Subject."),
            (self.otp_sender, "Please enter OTP Sender."),
        )

        for widget, message in fields:
            if not widget.text().strip():
                self.warn(message, widget)
                return False

        try:
            port = int(self.mail_port.text().strip())
            if port < 1 or port > 65535:
                raise ValueError
        except ValueError:
            self.warn(
                "Mail Port must be a valid number between 1 and 65535.",
                self.mail_port,
            )
            return False

        return True

    # =========================================================
    # Application Settings - Save / Update
    # =========================================================

    def save_application_settings(self):
        if not self.validate_application_fields():
            return

        invoice_path = self.invoice_path.text().strip()
        flatfile_path = self.flatfile_path.text().strip()
        asn_barcode_path = self.asn_barcode_path.text().strip()
        portal_userid = self.portal_userid.text().strip()
        portal_password = self.portal_password.text()

        connection = None
        cursor = None
        was_new = self.settings_id is None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            if self.settings_id is None:
                # Check for an exact system row first.
                cursor.execute(
                    """
                    SELECT TOP 1 ID
                    FROM dbo.SETTINGS
                    WHERE LTRIM(RTRIM(SYSTEM_NAME)) = LTRIM(RTRIM(?))
                    ORDER BY ID DESC
                    """,
                    self.system_name,
                )
                existing = cursor.fetchone()

                # If there is already a configuration row for this
                # application, reuse it instead of inserting a duplicate.
                if not existing:
                    cursor.execute(
                        """
                        SELECT TOP 1 ID
                        FROM dbo.SETTINGS
                        ORDER BY ID DESC
                        """
                    )
                    existing = cursor.fetchone()

                if existing:
                    self.settings_id = int(existing[0])

                else:
                    cursor.execute(
                        """
                        INSERT INTO dbo.SETTINGS
                        (
                            SYSTEM_NAME,
                            DS_INVOICE_PATH,
                            F_PATH,
                            ASN_BARCODE_PATH,
                            PORTAL_USERID,
                            PORTAL_PASSWORD,
                            CREATED_DATE
                        )
                        VALUES (?, ?, ?, ?, ?, ?, GETDATE())
                        """,
                        (
                            self.system_name,
                            invoice_path,
                            flatfile_path,
                            asn_barcode_path,
                            portal_userid,
                            portal_password,
                        ),
                    )

                    cursor.execute(
                        """
                        SELECT TOP 1 ID
                        FROM dbo.SETTINGS
                        WHERE SYSTEM_NAME = ?
                        ORDER BY ID DESC
                        """,
                        self.system_name,
                    )
                    row = cursor.fetchone()
                    if row:
                        self.settings_id = int(row[0])
            else:
                cursor.execute(
                    """
                    UPDATE dbo.SETTINGS
                    SET
                        DS_INVOICE_PATH = ?,
                        F_PATH = ?,
                        ASN_BARCODE_PATH = ?,
                        PORTAL_USERID = ?,
                        PORTAL_PASSWORD = ?,
                        UPDATED_DATE = GETDATE()
                    WHERE ID = ?
                    """,
                    (
                        invoice_path,
                        flatfile_path,
                        asn_barcode_path,
                        portal_userid,
                        portal_password,
                        self.settings_id,
                    ),
                )

            connection.commit()
            self.app_save_btn.setText("Update")

            QMessageBox.information(
                self,
                "Application Settings",
                "Application settings saved successfully."
                if was_new
                else "Application settings updated successfully.",
            )

        except Exception as error:
            if connection:
                try:
                    connection.rollback()
                except Exception:
                    pass

            QMessageBox.critical(
                self,
                "Application Settings Error",
                f"Unable to save application settings.\n\n{error}",
            )

        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    # =========================================================
    # Mail Settings - Save / Update
    # =========================================================

    def save_mail_settings(self):
        if not self.validate_mail_fields():
            return

        mail_server = self.mail_server.text().strip()
        mail_port = int(self.mail_port.text().strip())
        email_id = self.email_id.text().strip()
        email_password = self.email_password.text()
        otp_subject = self.otp_subject.text().strip()
        otp_sender = self.otp_sender.text().strip()

        connection = None
        cursor = None
        was_new = self.mail_settings_id is None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            if self.mail_settings_id is None:
                cursor.execute(
                    """
                    SELECT TOP 1 Id
                    FROM dbo.MailSettings
                    WHERE IsActive = 1
                    ORDER BY Id DESC
                    """
                )
                existing = cursor.fetchone()

                if existing:
                    self.mail_settings_id = int(existing[0])

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
                            ModifiedBy = ?,
                            ModifiedOn = GETDATE()
                        WHERE Id = ?
                        """,
                        (
                            mail_server,
                            mail_port,
                            email_id,
                            email_password,
                            otp_subject,
                            otp_sender,
                            "Admin",
                            self.mail_settings_id,
                        ),
                    )
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
                        VALUES (?, ?, ?, ?, ?, ?, 1, ?, GETDATE())
                        """,
                        (
                            mail_server,
                            mail_port,
                            email_id,
                            email_password,
                            otp_subject,
                            otp_sender,
                            "Admin",
                        ),
                    )

                    cursor.execute(
                        """
                        SELECT TOP 1 Id
                        FROM dbo.MailSettings
                        WHERE IsActive = 1
                        ORDER BY Id DESC
                        """
                    )
                    row = cursor.fetchone()
                    if row:
                        self.mail_settings_id = int(row[0])

            else:
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
                        ModifiedBy = ?,
                        ModifiedOn = GETDATE()
                    WHERE Id = ?
                    """,
                    (
                        mail_server,
                        mail_port,
                        email_id,
                        email_password,
                        otp_subject,
                        otp_sender,
                        "Admin",
                        self.mail_settings_id,
                    ),
                )

            connection.commit()
            self.mail_save_btn.setText("Update")

            QMessageBox.information(
                self,
                "Mail / OTP Settings",
                "Mail settings saved successfully."
                if was_new
                else "Mail settings updated successfully.",
            )

        except Exception as error:
            if connection:
                try:
                    connection.rollback()
                except Exception:
                    pass

            QMessageBox.critical(
                self,
                "Mail Settings Error",
                f"Unable to save mail settings.\n\n{error}",
            )

        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    # =========================================================
    # Other
    # =========================================================

    def clear_application_fields(self):
        self.invoice_path.clear()
        self.flatfile_path.clear()
        self.asn_barcode_path.clear()
        self.portal_userid.clear()
        self.portal_password.clear()

    def clear_mail_fields(self):
        self.mail_server.clear()
        self.mail_port.clear()
        self.email_id.clear()
        self.email_password.clear()
        self.otp_subject.clear()
        self.otp_sender.clear()

    def go_back(self):
        if callable(self.back_callback):
            self.back_callback()


# Backward-compatible import for existing code.
SettingsPage = ConfigurationPage
