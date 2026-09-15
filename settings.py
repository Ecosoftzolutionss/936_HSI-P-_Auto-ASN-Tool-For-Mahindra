import platform
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
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


class SettingsPage(QWidget):
    """
    HSI Automation Portal Settings page.

    IMPORTANT:
    This file must NOT contain:
        from settings import SettingsPage

    That import would make settings.py import itself and cause a
    circular-import error.
    """

    BG_COLOR = "#EEF1FA"
    WHITE = "#FFFFFF"
    PRIMARY = "#1457E6"
    TEXT_DARK = "#10182D"
    TEXT_GREY = "#71809E"
    CARD_COLOR = "#E4E9F7"

    def __init__(self, master=None, back_callback=None):
        super().__init__(master)

        self.back_callback = back_callback
        self.system_name = platform.node()

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
        header_layout.setSpacing(0)

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

        back_btn = QPushButton("←")
        back_btn.setFixedSize(40, 40)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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

        back_btn.clicked.connect(self.go_back)
        header_layout.addWidget(back_btn)

        root.addWidget(header)

        # -----------------------------------------------------
        # MAIN BACKGROUND
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

        bg_layout = QVBoxLayout(background)
        bg_layout.setContentsMargins(27, 27, 27, 27)
        bg_layout.setSpacing(0)

        # -----------------------------------------------------
        # SETTINGS CARD
        # -----------------------------------------------------

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

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(15, 12, 15, 16)
        card_layout.setSpacing(0)

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
        card_layout.addWidget(heading)

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
        card_layout.addWidget(description)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(
            "background: #6C8FEF; border: none;"
        )

        card_layout.addSpacing(10)
        card_layout.addWidget(line)
        card_layout.addSpacing(10)

        # -----------------------------------------------------
        # FORM
        # -----------------------------------------------------

        form = QFrame()
        form.setStyleSheet(
            """
            QFrame {
                background: transparent;
                border: none;
            }
            """
        )

        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(10)

        # Printer
        self.printer_combo = QComboBox()
        self.printer_combo.setMinimumHeight(32)
        self.printer_combo.setStyleSheet(self.input_style())

        self.load_printers()

        form_layout.addLayout(
            self.create_row(
                "Printers",
                self.printer_combo,
            )
        )

        # Invoice path
        self.invoice_path = QLineEdit()
        self.invoice_path.setMinimumHeight(32)
        self.invoice_path.setPlaceholderText(
            "Select invoice path"
        )
        self.invoice_path.setStyleSheet(
            self.input_style()
        )

        invoice_browse = QPushButton("📁 Browse")
        invoice_browse.setFixedSize(90, 32)
        invoice_browse.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        invoice_browse.setStyleSheet(
            self.browse_style()
        )
        invoice_browse.clicked.connect(
            lambda: self.browse_folder(self.invoice_path)
        )

        form_layout.addLayout(
            self.create_path_row(
                "Invoice Path",
                self.invoice_path,
                invoice_browse,
            )
        )

        # Flatfile path
        self.flatfile_path = QLineEdit()
        self.flatfile_path.setMinimumHeight(32)
        self.flatfile_path.setPlaceholderText(
            "Select flatfile path"
        )
        self.flatfile_path.setStyleSheet(
            self.input_style()
        )

        flatfile_browse = QPushButton("📁 Browse")
        flatfile_browse.setFixedSize(90, 32)
        flatfile_browse.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        flatfile_browse.setStyleSheet(
            self.browse_style()
        )
        flatfile_browse.clicked.connect(
            lambda: self.browse_folder(self.flatfile_path)
        )

        form_layout.addLayout(
            self.create_path_row(
                "Flatfile Path",
                self.flatfile_path,
                flatfile_browse,
            )
        )

        card_layout.addWidget(form)

        # -----------------------------------------------------
        # BOTTOM LINE
        # -----------------------------------------------------

        bottom_line = QFrame()
        bottom_line.setFixedHeight(1)
        bottom_line.setStyleSheet(
            "background: #6C8FEF; border: none;"
        )

        card_layout.addSpacing(10)
        card_layout.addWidget(bottom_line)
        card_layout.addSpacing(15)

        # -----------------------------------------------------
        # BUTTONS
        # -----------------------------------------------------

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedSize(72, 34)
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
        clear_btn.clicked.connect(self.clear_fields)

        update_btn = QPushButton("Update")
        update_btn.setFixedSize(72, 34)
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
        update_btn.clicked.connect(self.save_settings)

        buttons.addWidget(clear_btn)
        buttons.addSpacing(10)
        buttons.addWidget(update_btn)

        card_layout.addLayout(buttons)

        bg_layout.addWidget(card)
        bg_layout.addStretch()

        root.addWidget(background, 1)

    # =========================================================
    # PRINTERS
    # =========================================================

    def load_printers(self):
        try:
            if QPrinterInfo is not None:
                printers = QPrinterInfo.availablePrinters()

                for printer in printers:
                    name = printer.printerName()

                    if name:
                        self.printer_combo.addItem(
                            name
                        )

        except Exception as error:
            print(
                "Printer enumeration warning:",
                repr(error),
            )

        if self.printer_combo.count() == 0:
            self.printer_combo.addItem(
                "Microsoft Print to PDF"
            )

    # =========================================================
    # ROW HELPERS
    # =========================================================

    def create_row(self, label_text, widget):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        label = QLabel(label_text)
        label.setFixedWidth(90)
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

        row.addWidget(label)
        row.addWidget(widget, 1)

        return row

    def create_path_row(
        self,
        label_text,
        edit,
        button,
    ):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        label = QLabel(label_text)
        label.setFixedWidth(90)
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

        row.addWidget(label)
        row.addWidget(edit, 1)
        row.addWidget(button)

        return row

    # =========================================================
    # STYLES
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
    # DATABASE - LOAD
    # =========================================================

    def load_settings(self):
        connection = None
        cursor = None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT TOP 1
                    INV_PRINTER,
                    DS_INVOICE_PATH,
                    F_PATH
                FROM dbo.SETTINGS
                WHERE SYSTEM_NAME = ?
                """,
                self.system_name,
            )

            row = cursor.fetchone()

            if row:
                printer = str(
                    row[0] or ""
                ).strip()

                invoice_path = str(
                    row[1] or ""
                ).strip()

                flatfile_path = str(
                    row[2] or ""
                ).strip()

                if printer:
                    index = self.printer_combo.findText(
                        printer,
                        Qt.MatchFlag.MatchFixedString,
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

                self.invoice_path.setText(
                    invoice_path
                )

                self.flatfile_path.setText(
                    flatfile_path
                )

        except Exception as error:
            QMessageBox.warning(
                self,
                "Settings",
                "Unable to load settings from database.\n\n"
                f"{error}",
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
    # DATABASE - SAVE
    # =========================================================

    def save_settings(self):
        printer = self.printer_combo.currentText().strip()
        invoice_path = self.invoice_path.text().strip()
        flatfile_path = self.flatfile_path.text().strip()

        if not invoice_path:
            QMessageBox.warning(
                self,
                "Validation",
                "Please enter Invoice Path.",
            )
            self.invoice_path.setFocus()
            return

        if not flatfile_path:
            QMessageBox.warning(
                self,
                "Validation",
                "Please enter Flatfile Path.",
            )
            self.flatfile_path.setFocus()
            return

        connection = None
        cursor = None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT COUNT(1)
                FROM dbo.SETTINGS
                WHERE SYSTEM_NAME = ?
                """,
                self.system_name,
            )

            row = cursor.fetchone()
            exists = bool(row and row[0] > 0)

            if exists:
                cursor.execute(
                    """
                    UPDATE dbo.SETTINGS
                    SET
                        INV_PRINTER = ?,
                        DS_INVOICE_PATH = ?,
                        F_PATH = ?
                    WHERE SYSTEM_NAME = ?
                    """,
                    printer,
                    invoice_path,
                    flatfile_path,
                    self.system_name,
                )

            else:
                cursor.execute(
                    """
                    INSERT INTO dbo.SETTINGS
                    (
                        SYSTEM_NAME,
                        INV_PRINTER,
                        DS_INVOICE_PATH,
                        F_PATH
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    self.system_name,
                    printer,
                    invoice_path,
                    flatfile_path,
                )

            connection.commit()

            QMessageBox.information(
                self,
                "Settings",
                "Settings updated successfully.",
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
                "Failed to save settings.\n\n"
                f"{error}",
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
    # BROWSE
    # =========================================================

    def browse_folder(self, target):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder",
        )

        if folder:
            target.setText(folder)

    # =========================================================
    # CLEAR
    # =========================================================

    def clear_fields(self):
        self.invoice_path.clear()
        self.flatfile_path.clear()

        if self.printer_combo.count():
            self.printer_combo.setCurrentIndex(0)

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
    from PyQt6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = QMainWindow()
    window.setWindowTitle(
        "HSI Automation Portal - Settings"
    )
    window.resize(1347, 758)
    window.setMinimumSize(1100, 620)

    page = SettingsPage(
        window,
        back_callback=window.close,
    )

    window.setCentralWidget(page)
    window.show()

    sys.exit(app.exec())
