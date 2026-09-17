import platform
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QFileDialog,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

try:
    from PyQt6.QtPrintSupport import QPrinterInfo
except ImportError:
    QPrinterInfo = None

from database import get_connection


# =========================================================
# SETTINGS PAGE
# =========================================================

class SettingsPage(QWidget):

    """
    HSI Automation Portal Settings Page

    Database table:
        dbo.SETTINGS

    Fields:
        ID
        SYSTEM_NAME
        INV_PRINTER
        DS_INVOICE_PATH
        F_PATH
        ASN_BARCODE_PATH
        PORTAL_USERID
        PORTAL_PASSWORD
        CREATED_DATE
        UPDATED_DATE
    """

    # =====================================================
    # COLORS
    # =====================================================

    BG_COLOR = "#EEF1FA"
    WHITE = "#FFFFFF"
    PRIMARY = "#1457E6"
    TEXT_DARK = "#10182D"
    TEXT_GREY = "#71809E"
    CARD_COLOR = "#E4E9F7"

    # =====================================================
    # CONSTRUCTOR
    # =====================================================

    def __init__(
        self,
        master=None,
        back_callback=None
    ):

        super().__init__(master)

        self.back_callback = back_callback

        # -------------------------------------------------
        # CURRENT COMPUTER NAME
        # -------------------------------------------------

        self.system_name = platform.node()

        # -------------------------------------------------
        # DATABASE ROW ID
        # Used for reliable UPDATE
        # -------------------------------------------------

        self.settings_id = None

        # -------------------------------------------------
        # STYLE
        # -------------------------------------------------

        self.setStyleSheet(
            f"""
            QWidget {{
                font-family: "Segoe UI";
                color: {self.TEXT_DARK};
            }}
            """
        )

        # -------------------------------------------------
        # CREATE UI
        # -------------------------------------------------

        self.create_ui()

        # -------------------------------------------------
        # LOAD DATABASE SETTINGS
        # -------------------------------------------------

        self.load_settings()

    # =========================================================
    # CREATE UI
    # =========================================================

    def create_ui(self):

        root = QVBoxLayout(self)

        root.setContentsMargins(
            0,
            0,
            0,
            0
        )

        root.setSpacing(0)

        # =====================================================
        # HEADER
        # =====================================================

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

        header_layout.setContentsMargins(
            20,
            0,
            20,
            0
        )

        header_layout.setSpacing(0)

        # -----------------------------------------------------
        # HEADER TITLE
        # -----------------------------------------------------

        title = QLabel("Settings")

        title.setStyleSheet(
            """
            QLabel {
                color: #10182D;
                font-size: 18px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
            """
        )

        header_layout.addWidget(title)

        header_layout.addStretch()

        # -----------------------------------------------------
        # BACK BUTTON
        # -----------------------------------------------------

        back_btn = QPushButton("←")

        back_btn.setFixedSize(
            40,
            40
        )

        back_btn.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        back_btn.setToolTip("Back")

        back_btn.setStyleSheet(
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

            QPushButton:pressed {
                background: #0F3DA0;
            }
            """
        )

        back_btn.clicked.connect(
            self.go_back
        )

        header_layout.addWidget(
            back_btn
        )

        root.addWidget(
            header
        )

        # =====================================================
        # MAIN BACKGROUND
        # =====================================================

        background = QFrame()

        background.setStyleSheet(
            f"""
            QFrame {{
                background: {self.BG_COLOR};
                border: none;
            }}
            """
        )

        bg_layout = QVBoxLayout(
            background
        )

        bg_layout.setContentsMargins(
            27,
            27,
            27,
            27
        )

        bg_layout.setSpacing(0)

        # =====================================================
        # SETTINGS CARD
        # =====================================================

        card = QFrame()

        card.setStyleSheet(
            f"""
            QFrame {{
                background: {self.CARD_COLOR};
                border: none;
                border-radius: 8px;
            }}
            """
        )

        card_layout = QVBoxLayout(
            card
        )

        card_layout.setContentsMargins(
            15,
            12,
            15,
            16
        )

        card_layout.setSpacing(0)

        # =====================================================
        # HEADING
        # =====================================================

        heading = QLabel("Settings")

        heading.setStyleSheet(
            """
            QLabel {
                color: #25324A;
                font-size: 22px;
                font-weight: 600;
                background: transparent;
                border: none;
            }
            """
        )

        card_layout.addWidget(
            heading
        )

        # =====================================================
        # DESCRIPTION
        # =====================================================

        description = QLabel(
            "Configure system paths and printer settings."
        )

        description.setStyleSheet(
            """
            QLabel {
                color: #5F6B80;
                font-size: 12px;
                background: transparent;
                border: none;
            }
            """
        )

        card_layout.addWidget(
            description
        )

        # =====================================================
        # TOP LINE
        # =====================================================

        line = QFrame()

        line.setFixedHeight(1)

        line.setStyleSheet(
            """
            background: #6C8FEF;
            border: none;
            """
        )

        card_layout.addSpacing(10)

        card_layout.addWidget(
            line
        )

        card_layout.addSpacing(10)

        # =====================================================
        # SETTINGS FORM
        # =====================================================

        form = QFrame()

        form.setStyleSheet(
            """
            QFrame {
                background: transparent;
                border: none;
            }
            """
        )

        form_layout = QVBoxLayout(
            form
        )

        form_layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        form_layout.setSpacing(10)

        # =====================================================
        # PRINTER
        # =====================================================

        self.printer_combo = QComboBox()

        self.printer_combo.setMinimumHeight(
            32
        )

        self.printer_combo.setStyleSheet(
            self.input_style()
        )

        self.load_printers()

        form_layout.addLayout(
            self.create_row(
                "Printers",
                self.printer_combo
            )
        )

        # =====================================================
        # INVOICE PATH
        # =====================================================

        self.invoice_path = QLineEdit()

        self.invoice_path.setMinimumHeight(
            32
        )

        self.invoice_path.setPlaceholderText(
            "Select invoice path"
        )

        self.invoice_path.setStyleSheet(
            self.input_style()
        )

        invoice_browse = QPushButton(
            "📁 Browse"
        )

        invoice_browse.setFixedSize(
            90,
            32
        )

        invoice_browse.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        invoice_browse.setStyleSheet(
            self.browse_style()
        )

        invoice_browse.clicked.connect(
            lambda: self.browse_folder(
                self.invoice_path
            )
        )

        form_layout.addLayout(
            self.create_path_row(
                "Invoice Path",
                self.invoice_path,
                invoice_browse
            )
        )

        # =====================================================
        # FLATFILE PATH
        # =====================================================

        self.flatfile_path = QLineEdit()

        self.flatfile_path.setMinimumHeight(
            32
        )

        self.flatfile_path.setPlaceholderText(
            "Select flatfile path"
        )

        self.flatfile_path.setStyleSheet(
            self.input_style()
        )

        flatfile_browse = QPushButton(
            "📁 Browse"
        )

        flatfile_browse.setFixedSize(
            90,
            32
        )

        flatfile_browse.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        flatfile_browse.setStyleSheet(
            self.browse_style()
        )

        flatfile_browse.clicked.connect(
            lambda: self.browse_folder(
                self.flatfile_path
            )
        )

        form_layout.addLayout(
            self.create_path_row(
                "Flatfile Path",
                self.flatfile_path,
                flatfile_browse
            )
        )

        # =====================================================
        # ASN BARCODE PATH
        # =====================================================

        self.asn_barcode_path = QLineEdit()

        self.asn_barcode_path.setMinimumHeight(
            32
        )

        self.asn_barcode_path.setPlaceholderText(
            "Select ASN Barcode path"
        )

        self.asn_barcode_path.setStyleSheet(
            self.input_style()
        )

        asn_barcode_browse = QPushButton(
            "📁 Browse"
        )

        asn_barcode_browse.setFixedSize(
            90,
            32
        )

        asn_barcode_browse.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        asn_barcode_browse.setStyleSheet(
            self.browse_style()
        )

        asn_barcode_browse.clicked.connect(
            lambda: self.browse_folder(
                self.asn_barcode_path
            )
        )

        form_layout.addLayout(
            self.create_path_row(
                "ASN Barcode Path",
                self.asn_barcode_path,
                asn_barcode_browse
            )
        )

        # =====================================================
        # ADD FORM
        # =====================================================

        card_layout.addWidget(
            form
        )

        # =====================================================
        # CREDENTIALS LINE
        # =====================================================

        credentials_line = QFrame()

        credentials_line.setFixedHeight(
            1
        )

        credentials_line.setStyleSheet(
            """
            background: #6C8FEF;
            border: none;
            """
        )

        card_layout.addSpacing(
            18
        )

        card_layout.addWidget(
            credentials_line
        )

        card_layout.addSpacing(
            12
        )

        # =====================================================
        # CREDENTIALS TITLE
        # =====================================================

        credentials_title = QLabel(
            "Mahindra Portal Credentials"
        )

        credentials_title.setStyleSheet(
            """
            QLabel {
                color: #25324A;
                font-size: 15px;
                font-weight: 600;
                background: transparent;
                border: none;
            }
            """
        )

        card_layout.addWidget(
            credentials_title
        )

        card_layout.addSpacing(
            8
        )

        # =====================================================
        # CREDENTIALS FORM
        # =====================================================

        credentials_form = QFrame()

        credentials_form.setStyleSheet(
            """
            QFrame {
                background: transparent;
                border: none;
            }
            """
        )

        credentials_layout = QVBoxLayout(
            credentials_form
        )

        credentials_layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        credentials_layout.setSpacing(
            10
        )

        # =====================================================
        # PORTAL USER ID
        # =====================================================

        self.portal_userid = QLineEdit()

        self.portal_userid.setMinimumHeight(
            32
        )

        self.portal_userid.setPlaceholderText(
            "Enter Mahindra portal User ID"
        )

        self.portal_userid.setStyleSheet(
            self.input_style()
        )

        credentials_layout.addLayout(
            self.create_row(
                "Portal User ID",
                self.portal_userid
            )
        )

        # =====================================================
        # PORTAL PASSWORD
        # =====================================================

        self.portal_password = QLineEdit()

        self.portal_password.setMinimumHeight(
            32
        )

        self.portal_password.setPlaceholderText(
            "Enter Mahindra portal Password"
        )

        # -----------------------------------------------------
        # SHOW STORED PASSWORD
        # -----------------------------------------------------

        self.portal_password.setEchoMode(
            QLineEdit.EchoMode.Normal
        )

        self.portal_password.setStyleSheet(
            self.input_style()
        )

        credentials_layout.addLayout(
            self.create_row(
                "Portal Password",
                self.portal_password
            )
        )

        card_layout.addWidget(
            credentials_form
        )

        # =====================================================
        # BOTTOM LINE
        # =====================================================

        bottom_line = QFrame()

        bottom_line.setFixedHeight(
            1
        )

        bottom_line.setStyleSheet(
            """
            background: #6C8FEF;
            border: none;
            """
        )

        card_layout.addSpacing(
            10
        )

        card_layout.addWidget(
            bottom_line
        )

        card_layout.addSpacing(
            15
        )

        # =====================================================
        # BUTTONS
        # =====================================================

        buttons = QHBoxLayout()

        buttons.setContentsMargins(
            0,
            0,
            0,
            0
        )

        buttons.addStretch()

        # =====================================================
        # CLEAR
        # =====================================================

        clear_btn = QPushButton(
            "Clear"
        )

        clear_btn.setFixedSize(
            72,
            34
        )

        clear_btn.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        clear_btn.setStyleSheet(
            """
            QPushButton {
                background: #FFFFFF;
                color: #25324A;
                border: 1px solid #D6DCE8;
                border-radius: 3px;
                font-size: 11px;
            }

            QPushButton:hover {
                background: #F5F7FB;
            }
            """
        )

        clear_btn.clicked.connect(
            self.clear_fields
        )

        # =====================================================
        # UPDATE
        # =====================================================

        update_btn = QPushButton(
            "Update"
        )

        update_btn.setFixedSize(
            72,
            34
        )

        update_btn.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        update_btn.setStyleSheet(
            """
            QPushButton {
                background: #1457E6;
                color: #FFFFFF;
                border: none;
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
            }

            QPushButton:hover {
                background: #0E48C7;
            }

            QPushButton:pressed {
                background: #0B3BA5;
            }
            """
        )

        update_btn.clicked.connect(
            self.save_settings
        )

        buttons.addWidget(
            clear_btn
        )

        buttons.addSpacing(
            10
        )

        buttons.addWidget(
            update_btn
        )

        card_layout.addLayout(
            buttons
        )

        # =====================================================
        # ADD CARD
        # =====================================================

        bg_layout.addWidget(
            card
        )

        bg_layout.addStretch()

        root.addWidget(
            background,
            1
        )

    # =========================================================
    # LOAD PRINTERS
    # =========================================================

    def load_printers(self):

        try:

            if QPrinterInfo is not None:

                printers = (
                    QPrinterInfo.availablePrinters()
                )

                for printer in printers:

                    name = printer.printerName()

                    if name:

                        self.printer_combo.addItem(
                            name
                        )

        except Exception as error:

            print(
                "Printer enumeration warning:",
                repr(error)
            )

        # -----------------------------------------------------
        # FALLBACK PRINTER
        # -----------------------------------------------------

        if self.printer_combo.count() == 0:

            self.printer_combo.addItem(
                "Microsoft Print to PDF"
            )

    # =========================================================
    # ROW HELPER
    # =========================================================

    def create_row(
        self,
        label_text,
        widget
    ):

        row = QHBoxLayout()

        row.setContentsMargins(
            0,
            0,
            0,
            0
        )

        row.setSpacing(
            12
        )

        label = QLabel(
            label_text
        )

        # -----------------------------------------------------
        # Wider label for all fields
        # -----------------------------------------------------

        label.setFixedWidth(
            100
        )

        label.setStyleSheet(
            """
            QLabel {
                color: #25324A;
                font-size: 11px;
                font-weight: 600;
                background: transparent;
                border: none;
            }
            """
        )

        row.addWidget(
            label
        )

        row.addWidget(
            widget,
            1
        )

        return row

    # =========================================================
    # PATH ROW HELPER
    # =========================================================

    def create_path_row(
        self,
        label_text,
        edit,
        button
    ):

        row = QHBoxLayout()

        row.setContentsMargins(
            0,
            0,
            0,
            0
        )

        row.setSpacing(
            8
        )

        label = QLabel(
            label_text
        )

        # -----------------------------------------------------
        # ASN BARCODE PATH NEEDS MORE SPACE
        # -----------------------------------------------------

        label.setFixedWidth(
            100
        )

        label.setStyleSheet(
            """
            QLabel {
                color: #25324A;
                font-size: 11px;
                font-weight: 600;
                background: transparent;
                border: none;
            }
            """
        )

        row.addWidget(
            label
        )

        row.addWidget(
            edit,
            1
        )

        row.addWidget(
            button
        )

        return row

    # =========================================================
    # INPUT STYLE
    # =========================================================

    def input_style(self):

        return """
            QLineEdit, QComboBox {
                background: #FFFFFF;
                color: #25324A;
                border: 1px solid #D5DBE7;
                border-radius: 4px;
                padding: 0 10px;
                font-size: 10px;
            }

            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #4D7DF0;
            }

            QComboBox::drop-down {
                width: 25px;
                border: none;
            }
        """

    # =========================================================
    # BROWSE BUTTON STYLE
    # =========================================================

    def browse_style(self):

        return """
            QPushButton {
                background: #FFFFFF;
                color: #25324A;
                border: 1px solid #D5DBE7;
                border-radius: 4px;
                font-size: 9px;
            }

            QPushButton:hover {
                background: #F5F7FB;
            }

            QPushButton:pressed {
                background: #E9EDF5;
            }
        """

    # =========================================================
    # DATABASE - LOAD SETTINGS
    # =========================================================

    def load_settings(self):

        connection = None
        cursor = None

        try:

            connection = get_connection()

            cursor = connection.cursor()

            print("")
            print("=" * 70)
            print("LOADING SETTINGS")
            print("=" * 70)

            print(
                "CURRENT SYSTEM NAME :",
                self.system_name
            )

            # =================================================
            # FIRST:
            # SEARCH CURRENT SYSTEM
            # =================================================

            cursor.execute(
                """
                SELECT TOP 1
                    ID,
                    SYSTEM_NAME,
                    INV_PRINTER,
                    DS_INVOICE_PATH,
                    F_PATH,
                    ASN_BARCODE_PATH,
                    PORTAL_USERID,
                    PORTAL_PASSWORD
                FROM dbo.SETTINGS
                WHERE SYSTEM_NAME = ?
                ORDER BY ID DESC
                """,
                self.system_name
            )

            row = cursor.fetchone()

            # =================================================
            # FALLBACK:
            # IF CURRENT SYSTEM NOT FOUND
            # LOAD LATEST SETTINGS
            # =================================================

            if not row:

                print(
                    "Current system settings not found."
                )

                print(
                    "Loading latest SETTINGS row..."
                )

                cursor.execute(
                    """
                    SELECT TOP 1
                        ID,
                        SYSTEM_NAME,
                        INV_PRINTER,
                        DS_INVOICE_PATH,
                        F_PATH,
                        ASN_BARCODE_PATH,
                        PORTAL_USERID,
                        PORTAL_PASSWORD
                    FROM dbo.SETTINGS
                    ORDER BY ID DESC
                    """
                )

                row = cursor.fetchone()

            # =================================================
            # NO DATA
            # =================================================

            if not row:

                print(
                    "No data found in dbo.SETTINGS"
                )

                QMessageBox.warning(
                    self,
                    "Settings",
                    "No settings data found in dbo.SETTINGS."
                )

                return

            # =================================================
            # SAVE DATABASE ROW ID
            # =================================================

            self.settings_id = row[0]

            # =================================================
            # SYSTEM NAME
            # =================================================

            database_system_name = str(
                row[1] or ""
            ).strip()

            # -------------------------------------------------
            # If fallback row was used,
            # keep its SYSTEM_NAME for UPDATE
            # -------------------------------------------------

            if database_system_name:

                self.system_name = (
                    database_system_name
                )

            # =================================================
            # PRINTER
            # =================================================

            printer = str(
                row[2] or ""
            ).strip()

            # =================================================
            # INVOICE PATH
            # =================================================

            invoice_path = str(
                row[3] or ""
            ).strip()

            # =================================================
            # FLATFILE PATH
            # =================================================

            flatfile_path = str(
                row[4] or ""
            ).strip()

            # =================================================
            # ASN BARCODE PATH
            # =================================================

            asn_barcode_path = str(
                row[5] or ""
            ).strip()

            # =================================================
            # PORTAL USER ID
            # =================================================

            portal_userid = str(
                row[6] or ""
            ).strip()

            # =================================================
            # PORTAL PASSWORD
            # =================================================

            portal_password = str(
                row[7] or ""
            )

            # =================================================
            # DEBUG OUTPUT
            # =================================================

            print("-" * 70)

            print(
                "SETTINGS ID       :",
                self.settings_id
            )

            print(
                "SYSTEM NAME       :",
                database_system_name
            )

            print(
                "INV PRINTER       :",
                printer
            )

            print(
                "INVOICE PATH      :",
                invoice_path
            )

            print(
                "FLATFILE PATH     :",
                flatfile_path
            )

            print(
                "ASN BARCODE PATH  :",
                asn_barcode_path
            )

            print(
                "PORTAL USER ID    :",
                portal_userid
            )

            print(
                "PORTAL PASSWORD   :",
                "********"
                if portal_password
                else "EMPTY"
            )

            print("-" * 70)

            # =================================================
            # SET PRINTER
            # =================================================

            if printer:

                index = (
                    self.printer_combo.findText(
                        printer,
                        Qt.MatchFlag.MatchFixedString
                    )
                )

                if index >= 0:

                    self.printer_combo.setCurrentIndex(
                        index
                    )

                else:

                    self.printer_combo.addItem(
                        printer
                    )

                    self.printer_combo.setCurrentText(
                        printer
                    )

            # =================================================
            # SET INVOICE PATH
            # =================================================

            self.invoice_path.setText(
                invoice_path
            )

            # =================================================
            # SET FLATFILE PATH
            # =================================================

            self.flatfile_path.setText(
                flatfile_path
            )

            # =================================================
            # SET ASN BARCODE PATH
            # =================================================

            self.asn_barcode_path.setText(
                asn_barcode_path
            )

            # =================================================
            # SET PORTAL USER ID
            # =================================================

            self.portal_userid.setText(
                portal_userid
            )

            # =================================================
            # SET PORTAL PASSWORD
            # =================================================

            self.portal_password.setText(
                portal_password
            )

            print(
                "SETTINGS LOADED SUCCESSFULLY"
            )

            print(
                "=" * 70
            )

        except Exception as error:

            print("")
            print("=" * 70)
            print("SETTINGS LOAD FAILED")
            print("=" * 70)

            print(
                repr(error)
            )

            QMessageBox.critical(
                self,
                "Settings Error",
                "Unable to load settings from database.\n\n"
                f"{error}"
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
    # DATABASE - SAVE SETTINGS
    # =========================================================

    def save_settings(self):

        # =====================================================
        # GET VALUES
        # =====================================================

        printer = (
            self.printer_combo
            .currentText()
            .strip()
        )

        invoice_path = (
            self.invoice_path
            .text()
            .strip()
        )

        flatfile_path = (
            self.flatfile_path
            .text()
            .strip()
        )

        asn_barcode_path = (
            self.asn_barcode_path
            .text()
            .strip()
        )

        portal_userid = (
            self.portal_userid
            .text()
            .strip()
        )

        portal_password = (
            self.portal_password
            .text()
        )

        # =====================================================
        # VALIDATION
        # =====================================================

        if not invoice_path:

            QMessageBox.warning(
                self,
                "Validation",
                "Please enter Invoice Path."
            )

            self.invoice_path.setFocus()

            return

        if not flatfile_path:

            QMessageBox.warning(
                self,
                "Validation",
                "Please enter Flatfile Path."
            )

            self.flatfile_path.setFocus()

            return

        if not asn_barcode_path:

            QMessageBox.warning(
                self,
                "Validation",
                "Please enter ASN Barcode Path."
            )

            self.asn_barcode_path.setFocus()

            return

        if not portal_userid:

            QMessageBox.warning(
                self,
                "Validation",
                "Please enter Mahindra Portal User ID."
            )

            self.portal_userid.setFocus()

            return

        if not portal_password:

            QMessageBox.warning(
                self,
                "Validation",
                "Please enter Mahindra Portal Password."
            )

            self.portal_password.setFocus()

            return

        # =====================================================
        # DATABASE
        # =====================================================

        connection = None
        cursor = None

        try:

            connection = get_connection()

            cursor = connection.cursor()

            # =================================================
            # UPDATE USING ID
            # =================================================

            if self.settings_id is not None:

                print("")
                print(
                    "Updating SETTINGS ID:",
                    self.settings_id
                )

                cursor.execute(
                    """
                    UPDATE dbo.SETTINGS
                    SET
                        INV_PRINTER = ?,
                        DS_INVOICE_PATH = ?,
                        F_PATH = ?,
                        ASN_BARCODE_PATH = ?,
                        PORTAL_USERID = ?,
                        PORTAL_PASSWORD = ?,
                        UPDATED_DATE = GETDATE()
                    WHERE ID = ?
                    """,

                    (
                        printer,
                        invoice_path,
                        flatfile_path,
                        asn_barcode_path,
                        portal_userid,
                        portal_password,
                        self.settings_id
                    )
                )

            # =================================================
            # IF ID NOT AVAILABLE:
            # SEARCH BY SYSTEM NAME
            # =================================================

            else:

                cursor.execute(
                    """
                    SELECT TOP 1 ID
                    FROM dbo.SETTINGS
                    WHERE SYSTEM_NAME = ?
                    ORDER BY ID DESC
                    """,
                    self.system_name
                )

                row = cursor.fetchone()

                if row:

                    self.settings_id = row[0]

                    cursor.execute(
                        """
                        UPDATE dbo.SETTINGS
                        SET
                            INV_PRINTER = ?,
                            DS_INVOICE_PATH = ?,
                            F_PATH = ?,
                            ASN_BARCODE_PATH = ?,
                            PORTAL_USERID = ?,
                            PORTAL_PASSWORD = ?,
                            UPDATED_DATE = GETDATE()
                        WHERE ID = ?
                        """,

                        (
                            printer,
                            invoice_path,
                            flatfile_path,
                            asn_barcode_path,
                            portal_userid,
                            portal_password,
                            self.settings_id
                        )
                    )

                # =============================================
                # INSERT NEW
                # =============================================

                else:

                    cursor.execute(
                        """
                        INSERT INTO dbo.SETTINGS
                        (
                            SYSTEM_NAME,
                            INV_PRINTER,
                            DS_INVOICE_PATH,
                            F_PATH,
                            ASN_BARCODE_PATH,
                            PORTAL_USERID,
                            PORTAL_PASSWORD,
                            CREATED_DATE
                        )
                        VALUES
                        (
                            ?,
                            ?,
                            ?,
                            ?,
                            ?,
                            ?,
                            ?,
                            GETDATE()
                        )
                        """,

                        (
                            self.system_name,
                            printer,
                            invoice_path,
                            flatfile_path,
                            asn_barcode_path,
                            portal_userid,
                            portal_password
                        )
                    )

            # =================================================
            # COMMIT
            # =================================================

            connection.commit()

            print(
                "SETTINGS SAVED SUCCESSFULLY"
            )

            # =================================================
            # RELOAD
            # =================================================

            self.load_settings()

            QMessageBox.information(
                self,
                "Settings",
                "Settings updated successfully."
            )

        except Exception as error:

            print("")
            print(
                "=" * 70
            )

            print(
                "SETTINGS SAVE FAILED"
            )

            print(
                "=" * 70
            )

            print(
                repr(error)
            )

            if connection:

                try:
                    connection.rollback()

                except Exception:
                    pass

            QMessageBox.critical(
                self,
                "Database Error",
                "Failed to save settings.\n\n"
                f"{error}"
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
    # BROWSE FOLDER
    # =========================================================

    def browse_folder(
        self,
        target
    ):

        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder"
        )

        if folder:

            target.setText(
                folder
            )

    # =========================================================
    # CLEAR
    # =========================================================

    def clear_fields(self):

        self.invoice_path.clear()

        self.flatfile_path.clear()

        self.asn_barcode_path.clear()

        self.portal_userid.clear()

        self.portal_password.clear()

        if self.printer_combo.count():

            self.printer_combo.setCurrentIndex(
                0
            )

    # =========================================================
    # BACK
    # =========================================================

    def go_back(self):

        if callable(
            self.back_callback
        ):

            self.back_callback()


# =============================================================
# STANDALONE TEST
# =============================================================

if __name__ == "__main__":

    app = QApplication(
        sys.argv
    )

    app.setStyle(
        "Fusion"
    )

    window = QMainWindow()

    window.setWindowTitle(
        "HSI Automation Portal - Settings"
    )

    window.resize(
        1347,
        758
    )

    window.setMinimumSize(
        1100,
        620
    )

    page = SettingsPage(
        window,
        back_callback=window.close
    )

    window.setCentralWidget(
        page
    )

    window.show()

    sys.exit(
        app.exec()
    )