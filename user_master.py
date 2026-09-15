from pathlib import Path

import bcrypt

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import get_connection


class Toast(QWidget):
    """PyQt6 replacement for the original CustomTkinter toast."""

    def __init__(self, parent, message, message_type="success", duration=3000):
        super().__init__(parent)
        self.setFixedSize(330, 72)

        data = {
            "success": ("Success", "✓", "#22C55E"),
            "error": ("Error", "!", "#EF4444"),
            "warning": ("Warning", "!", "#F59E0B"),
        }
        title, icon, accent = data.get(message_type, data["warning"])

        self.setStyleSheet("""
            Toast {
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
            }
        """)

        icon_frame = QFrame(self)
        icon_frame.setGeometry(14, 18, 34, 34)
        icon_frame.setStyleSheet(
            f"QFrame {{ background: {accent}; border-radius: 17px; }}"
        )

        icon_label = QLabel(icon, icon_frame)
        icon_label.setGeometry(0, 0, 34, 34)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("""
            QLabel {
                color: white;
                background: transparent;
                border: none;
                font-size: 17px;
                font-weight: bold;
            }
        """)

        title_label = QLabel(title, self)
        title_label.setGeometry(60, 8, 230, 22)
        title_label.setStyleSheet("""
            QLabel {
                color: #1F2937;
                background: transparent;
                border: none;
                font-size: 12px;
                font-weight: bold;
            }
        """)

        msg_label = QLabel(message, self)
        msg_label.setGeometry(60, 33, 245, 30)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet("""
            QLabel {
                color: #6B7280;
                background: transparent;
                border: none;
                font-size: 11px;
            }
        """)

        close_btn = QPushButton("×", self)
        close_btn.setGeometry(302, 6, 22, 22)
        close_btn.setStyleSheet("""
            QPushButton {
                color: #9CA3AF;
                background: transparent;
                border: none;
                font-size: 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background: #F3F4F6; }
        """)
        close_btn.clicked.connect(self.close)

        progress = QFrame(self)
        progress.setGeometry(0, 69, 330, 3)
        progress.setStyleSheet(
            f"QFrame {{ background: {accent}; border: none; }}"
        )

        self.show()
        self.raise_()
        QTimer.singleShot(duration, self.close)


class UserMasterPage(QWidget):
    """
    Full PyQt6 conversion of the supplied UserMasterPage.

    Preserves:
      - SQL loading of UserTypes, Departments and Users
      - Create / Update / Delete
      - BCrypt password hashing
      - Admin delete protection
      - Row selection and double-click edit
      - Pagination
      - Toast messages
      - Back callback
    """

    BG_COLOR = "#EEF1FA"
    WHITE = "#FFFFFF"
    PRIMARY = "#1457E6"
    TEXT_DARK = "#10182D"
    TEXT_GREY = "#71809E"
    CARD_COLOR = "#E4EAF9"
    BORDER_COLOR = "#78A0FF"
    HEADER_BG = "#E8EEFF"
    ROW_ALT = "#F7F9FC"
    EDIT_BG = "#EEF5FF"
    EDIT_HOVER = "#D9E9FF"
    EDIT_BORDER = "#C7DBFF"
    DELETE_BG = "#FFF0F0"
    DELETE_HOVER = "#FFE0E0"
    DELETE_BORDER = "#FFD0D0"

    def __init__(self, master=None, back_callback=None):
        super().__init__(master)

        self.back_callback = back_callback
        self.base_path = Path(__file__).resolve().parent

        self.editing_user_id = None
        self.selected_user_id = None
        self.all_users = []
        self._toast = None

        self.create_ui()
        self.load_user_types()
        self.load_departments()
        self.load_users()

    # =========================================================
    # UI HELPERS
    # =========================================================

    def make_button(self, text, width, height, bg, hover, fg="#FFFFFF"):
        button = QPushButton(text)
        button.setFixedSize(width, height)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                color: {fg};
                border: none;
                border-radius: 7px;
                font-size: 11px;
            }}
            QPushButton:hover {{ background: {hover}; }}
        """)
        return button

    def create_ui(self):
        self.setStyleSheet(f"""
            QWidget {{
                font-family: "Segoe UI";
                color: {self.TEXT_DARK};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # =====================================================
        # HEADER
        # =====================================================

        self.header = QFrame()
        self.header.setFixedHeight(70)
        self.header.setStyleSheet("background: #FFFFFF; border: none;")

        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(20, 0, 20, 0)

        # Logo
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(145, 48)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo_paths = [
            self.base_path / "assets" / "HSI_LOGO.png",
            self.base_path / "assets" / "HSI.png",
            self.base_path / "assets" / "Dashtoplogo.png",
        ]

        logo_path = next((p for p in logo_paths if p.exists()), None)

        if logo_path:
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                self.logo_label.setPixmap(
                    pixmap.scaled(
                        145,
                        48,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        else:
            self.logo_label.setText("HSI\nAUTOMATION PORTAL")
            self.logo_label.setStyleSheet("""
                QLabel {
                    color: #10182D;
                    font-size: 17px;
                    font-weight: bold;
                }
            """)

        header_layout.addWidget(self.logo_label)
        header_layout.addStretch()

        self.back_header_button = self.make_button(
            "←", 42, 42, "#2E6DEB", "#174FC5"
        )
        self.back_header_button.setFont(
            self.back_header_button.font()
        )
        self.back_header_button.setStyleSheet("""
            QPushButton {
                background: #2E6DEB;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton:hover { background: #174FC5; }
        """)
        self.back_header_button.clicked.connect(self.go_back)
        header_layout.addWidget(self.back_header_button)

        root.addWidget(self.header)

        # =====================================================
        # CONTENT
        # =====================================================

        self.content = QFrame()
        self.content.setStyleSheet(f"background: {self.BG_COLOR};")
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(44, 28, 44, 28)

        # =====================================================
        # MAIN CARD
        # =====================================================

        self.main_card = QFrame()
        self.main_card.setStyleSheet(
            f"QFrame {{ background: {self.CARD_COLOR}; border-radius: 8px; }}"
        )

        card_layout = QVBoxLayout(self.main_card)
        card_layout.setContentsMargins(24, 14, 24, 18)
        card_layout.setSpacing(0)

        self.title_label = QLabel("User Master")
        self.title_label.setStyleSheet("""
            QLabel {
                color: #10182D;
                background: transparent;
                font-size: 28px;
                font-weight: bold;
            }
        """)
        card_layout.addWidget(self.title_label)

        self.description_label = QLabel(
            "Create and manage users for the system."
        )
        self.description_label.setStyleSheet("""
            QLabel {
                color: #4F5565;
                background: transparent;
                font-size: 15px;
            }
        """)
        card_layout.addWidget(self.description_label)
        card_layout.addSpacing(18)

        # =====================================================
        # FORM
        # =====================================================

        self.form_frame = QFrame()
        self.form_frame.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border: 1px solid {self.BORDER_COLOR};
                border-radius: 6px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)

        form = QGridLayout(self.form_frame)
        form.setContentsMargins(22, 25, 22, 25)
        form.setHorizontalSpacing(35)
        form.setVerticalSpacing(10)

        label_style = """
            QLabel {
                color: #374151;
                background: transparent;
                border: none;
                font-size: 15px;
            }
        """

        self.username_label = QLabel("User Name")
        self.username_label.setStyleSheet(label_style)
        form.addWidget(self.username_label, 0, 0)

        self.username_entry = QLineEdit()
        self.username_entry.setPlaceholderText("Enter user name")
        self.username_entry.setMinimumHeight(38)
        self.username_entry.setMinimumWidth(445)
        self.username_entry.setStyleSheet(self.line_edit_style())
        form.addWidget(self.username_entry, 0, 1)

        self.password_label = QLabel("Password")
        self.password_label.setStyleSheet(label_style)
        form.addWidget(self.password_label, 1, 0)

        self.password_entry = QLineEdit()
        self.password_entry.setPlaceholderText("Enter password")
        self.password_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_entry.setMinimumHeight(38)
        self.password_entry.setMinimumWidth(445)
        self.password_entry.setStyleSheet(self.line_edit_style())
        form.addWidget(self.password_entry, 1, 1)

        self.user_type_label = QLabel("User Type")
        self.user_type_label.setStyleSheet(label_style)
        form.addWidget(self.user_type_label, 2, 0)

        self.user_type_combo = QComboBox()
        self.user_type_combo.setMinimumHeight(38)
        self.user_type_combo.setMinimumWidth(445)
        self.user_type_combo.setStyleSheet(self.combo_style())
        self.user_type_combo.addItem("Loading...")
        form.addWidget(self.user_type_combo, 2, 1)

        self.department_label = QLabel("Department")
        self.department_label.setStyleSheet(label_style)
        form.addWidget(self.department_label, 3, 0)

        self.department_combo = QComboBox()
        self.department_combo.setMinimumHeight(38)
        self.department_combo.setMinimumWidth(445)
        self.department_combo.setStyleSheet(self.combo_style())
        self.department_combo.addItem("Loading...")
        form.addWidget(self.department_combo, 3, 1)

        card_layout.addWidget(self.form_frame)
        card_layout.addSpacing(10)

        # =====================================================
        # BUTTONS
        # =====================================================

        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        button_layout.setSpacing(12)

        self.save_button = QPushButton("Save")
        self.save_button.setFixedSize(100, 38)
        self.save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_button.setStyleSheet("""
            QPushButton {
                background: #1457E6;
                color: white;
                border: none;
                border-radius: 7px;
                font-size: 11px;
            }
            QPushButton:hover { background: #0E48C7; }
        """)
        self.save_button.clicked.connect(self.save_user)

        self.reset_button = QPushButton("Clear")
        self.reset_button.setFixedSize(100, 38)
        self.reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_button.setStyleSheet("""
            QPushButton {
                background: white;
                color: #374151;
                border: 1px solid #D1D5DB;
                border-radius: 7px;
                font-size: 11px;
            }
            QPushButton:hover { background: #E5E7EB; }
        """)
        self.reset_button.clicked.connect(self.reset_form)

        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.reset_button)
        card_layout.addLayout(button_layout)
        card_layout.addSpacing(8)

        # =====================================================
        # SAVED USERS TABLE
        # =====================================================

        self.table_title = QLabel("User Lists")
        self.table_title.setStyleSheet("""
            QLabel {
                color: #10182D;
                background: transparent;
                font-size: 18px;
                font-weight: bold;
            }
        """)
        card_layout.addWidget(self.table_title)
        card_layout.addSpacing(8)

        self.create_users_table()

        # create_users_table() already adds the table_container
        # (which contains self.table_widget) to the main card.
        # Do not add self.table_widget a second time here.

        content_layout.addWidget(self.main_card, 1)
        root.addWidget(self.content, 1)

        # =====================================================
        # FOOTER
        # =====================================================

        self.footer = QLabel(
            "© 2025 HSI Automation Portal. All rights reserved."
        )
        self.footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer.setFixedHeight(25)
        self.footer.setStyleSheet(f"""
            QLabel {{
                color: {self.TEXT_GREY};
                background: {self.BG_COLOR};
                font-size: 9px;
            }}
        """)
        root.addWidget(self.footer)

    def line_edit_style(self):
        return """
            QLineEdit {
                background: white;
                color: #10182D;
                border: 1px solid #D4D9E2;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #78A0FF;
            }
        """

    def combo_style(self):
        return """
            QComboBox {
                background: white;
                color: #10182D;
                border: 1px solid #D4D9E2;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 14px;
            }
            QComboBox:focus {
                border: 1px solid #78A0FF;
            }
            QComboBox::drop-down {
                width: 32px;
                border: none;
            }
            QComboBox::down-arrow {
                width: 8px;
                height: 8px;
            }
            QComboBox QAbstractItemView {
                background: white;
                color: #10182D;
                selection-background-color: #E8EEFF;
                selection-color: #10182D;
                border: 1px solid #D4D9E2;
            }
        """

    # =========================================================
    # TABLE
    # =========================================================

    def create_users_table(self):
        self.table_widget = QTableWidget(0, 5)
        self.table_widget.setMinimumHeight(230)
        self.table_widget.setHorizontalHeaderLabels(
            ["S.No", "User Name", "User Type", "Department", "Actions"]
        )

        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table_widget.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.setShowGrid(False)
        self.table_widget.horizontalHeader().setFixedHeight(38)

        header = self.table_widget.horizontalHeader()
        header.setMinimumSectionSize(70)

        # =====================================================
        # FIXED / STABLE COLUMN ALIGNMENT
        # =====================================================
        # S.No       -> fixed and centered
        # User Name  -> takes remaining available width
        # User Type  -> fixed and centered
        # Department -> fixed and centered
        # Actions    -> fixed and centered
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)

        self.table_widget.setColumnWidth(0, 70)
        self.table_widget.setColumnWidth(2, 170)
        self.table_widget.setColumnWidth(3, 180)
        self.table_widget.setColumnWidth(4, 135)

        header.setStretchLastSection(False)

        self.table_widget.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.table_widget.setStyleSheet("""
            QTableWidget {
                background: white;
                alternate-background-color: #F7F9FC;
                color: #10182D;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 5px;
                border: none;
            }
            QTableWidget::item:selected {
                background: #DCE7FF;
                color: #10182D;
            }
            QHeaderView::section {
                background: #E8EEFF;
                color: #10182D;
                border: none;
                padding: 8px;
                font-size: 12px;
                font-weight: bold;
            }
            QScrollBar:vertical {
                width: 10px;
                background: #F8FAFC;
            }
            QScrollBar::handle:vertical {
                background: #CBD5E1;
                border-radius: 5px;
                min-height: 25px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.table_widget.itemSelectionChanged.connect(
            self.on_table_selection_changed
        )
        self.table_widget.cellDoubleClicked.connect(
            self.on_table_double_click
        )

        # Put table + pagination inside one white frame to match
        # the original layout.
        self.table_container = QFrame()
        self.table_container.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 6px;
            }
        """)

        container_layout = QVBoxLayout(self.table_container)
        container_layout.setContentsMargins(8, 8, 8, 8)
        container_layout.setSpacing(0)
        self.table_container.setMinimumHeight(250)

        container_layout.addWidget(self.table_widget, 1)

        # Add the complete table container to the card.
        card_layout = self.main_card.layout()
        card_layout.addWidget(self.table_container, 1)

    # =========================================================
    # LOAD USER TYPES
    # =========================================================

    def load_user_types(self):
        connection = None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute("""
                SELECT UserType
                FROM dbo.UserTypes
                WHERE IsActive = 1
                ORDER BY UserType
            """)

            rows = cursor.fetchall()

            user_types = [
                str(row[0]).strip()
                for row in rows
                if row[0] is not None
            ]

            self.user_type_combo.clear()

            if user_types:
                self.user_type_combo.addItem("Select User Type")
                self.user_type_combo.addItems(user_types)
            else:
                self.user_type_combo.addItem("No User Type")

        except Exception as error:
            print("User Type loading error:", error)
            self.user_type_combo.clear()
            self.user_type_combo.addItem("Unable to load")

        finally:
            if connection:
                connection.close()

    # =========================================================
    # LOAD DEPARTMENTS
    # =========================================================

    def load_departments(self):
        connection = None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute("""
                SELECT DepartmentName
                FROM Departments
                WHERE IsActive = 1
                ORDER BY DepartmentName
            """)

            rows = cursor.fetchall()

            departments = [
                str(row[0]).strip()
                for row in rows
                if row[0] is not None
            ]

            print("Departments loaded:", departments)

            self.department_combo.clear()

            if departments:
                self.department_combo.addItem("Select Department")
                self.department_combo.addItems(departments)
            else:
                self.department_combo.addItem("No Department")

        except Exception as error:
            print("Department loading error:", error)
            self.department_combo.clear()
            self.department_combo.addItem("Unable to load")

        finally:
            if connection:
                connection.close()

    # =========================================================
    # LOAD USERS
    # =========================================================

    def load_users(self):
        connection = None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute("""
                SELECT
                    UserId,
                    Username,
                    Role,
                    ISNULL(DepartmentName, '') AS DepartmentName
                FROM dbo.Users
                WHERE IsActive = 1
                ORDER BY UserId DESC
            """)

            rows = cursor.fetchall()

            print(f"Users loaded from database: {len(rows)}")

            self.all_users = [
                {
                    "user_id": int(row[0]),
                    "username": str(row[1] or ""),
                    "role": str(row[2] or ""),
                    "department": str(row[3] or ""),
                }
                for row in rows
            ]

            self.selected_user_id = None
            self.render_current_page()

        except Exception as error:
            print("Load users error:", error)
            self.show_toast(str(error), "error", 5000)

        finally:
            if connection:
                connection.close()

    # =========================================================
    # RENDER TABLE
    # =========================================================

    def render_current_page(self):
        # Pagination removed: display all active users in the table.
        total = len(self.all_users)
        start_index = 0
        page_users = self.all_users

        self.table_widget.setRowCount(0)

        for page_index, user in enumerate(page_users):
            row_index = self.table_widget.rowCount()
            self.table_widget.insertRow(row_index)
            self.table_widget.setRowHeight(row_index, 42)

            user_id = user["user_id"]

            values = [
                str(page_index + 1),
                user["username"],
                user["role"],
                user["department"],
            ]

            for col, value in enumerate(values):
                item = QTableWidgetItem(value)

                if col == 1:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                    )
                else:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                    )

                item.setData(Qt.ItemDataRole.UserRole, user_id)
                self.table_widget.setItem(
                    row_index,
                    col,
                    item,
                )

            # Actions cell
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)

            # Keep both action buttons exactly centered in the Actions column.
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setSpacing(6)
            action_layout.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            edit_button = QPushButton("✎")
            edit_button.setFixedSize(36, 30)
            edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_button.setStyleSheet("""
                QPushButton {
                    background: #EEF5FF;
                    color: #1457E6;
                    border: 1px solid #C7DBFF;
                    border-radius: 5px;
                    font-size: 15px;
                    font-weight: bold;
                }
                QPushButton:hover { background: #D9E9FF; }
            """)
            edit_button.clicked.connect(
                lambda checked=False, uid=user_id:
                self.open_user_for_edit(uid)
            )

            delete_button = QPushButton("🗑")
            delete_button.setFixedSize(36, 30)
            delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
            delete_button.setStyleSheet("""
                QPushButton {
                    background: #FFF0F0;
                    color: #DC3545;
                    border: 1px solid #FFD0D0;
                    border-radius: 5px;
                    font-size: 14px;
                }
                QPushButton:hover { background: #FFE0E0; }
            """)
            delete_button.clicked.connect(
                lambda checked=False, uid=user_id:
                self.delete_user_by_id(uid)
            )

            action_layout.addWidget(edit_button)
            action_layout.addWidget(delete_button)
            self.table_widget.setCellWidget(
                row_index,
                4,
                action_widget,
            )

        # Make header alignment match the body data.
        header = self.table_widget.horizontalHeader()

        header_item = self.table_widget.horizontalHeaderItem(0)
        if header_item is not None:
            header_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )

        header_item = self.table_widget.horizontalHeaderItem(1)
        if header_item is not None:
            header_item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )

        for col in (2, 3, 4):
            header_item = self.table_widget.horizontalHeaderItem(col)
            if header_item is not None:
                header_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter | Qt.AlignVCenter
                )

        self.table_widget.clearSelection()

    # =========================================================
    # SELECTION
    # =========================================================

    def on_table_selection_changed(self):
        row = self.table_widget.currentRow()

        if row < 0:
            self.selected_user_id = None
            return

        item = self.table_widget.item(row, 0)

        if item:
            self.selected_user_id = item.data(Qt.ItemDataRole.UserRole)

    def select_user_row(self, user_id):
        self.selected_user_id = user_id

        for row in range(self.table_widget.rowCount()):
            item = self.table_widget.item(row, 0)

            if item and item.data(Qt.ItemDataRole.UserRole) == user_id:
                self.table_widget.selectRow(row)
                return

    # =========================================================
    # DOUBLE CLICK
    # =========================================================

    def on_table_double_click(self, row, column):
        item = self.table_widget.item(row, 0)

        if item:
            user_id = item.data(Qt.ItemDataRole.UserRole)
            if user_id is not None:
                self.open_user_for_edit(int(user_id))

    def on_row_double_click(self, event=None):
        # Compatibility method from original implementation.
        return

    # =========================================================
    # OPEN USER FOR EDIT
    # =========================================================

    def open_user_for_edit(self, user_id):
        self.selected_user_id = user_id
        self.select_user_row(user_id)
        self.editing_user_id = user_id

        connection = None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute("""
                SELECT
                    Username,
                    Role,
                    ISNULL(DepartmentName, '')
                FROM dbo.Users
                WHERE UserId = ?
                  AND IsActive = 1
            """, user_id)

            row = cursor.fetchone()

            if not row:
                self.show_toast(
                    "User not found.",
                    "warning",
                )
                self.editing_user_id = None
                return

            self.username_entry.setText(row[0] or "")

            # Never display stored password.
            self.password_entry.clear()
            self.password_entry.setPlaceholderText(
                "Leave blank to keep current password"
            )

            self.set_combo_text(
                self.user_type_combo,
                row[1] or "Select User Type",
            )

            self.set_combo_text(
                self.department_combo,
                row[2] or "Select Department",
            )

            self.save_button.setText("Update")
            self.username_entry.setFocus()

        except Exception as error:
            print("Edit user error:", error)
            self.show_toast(
                str(error),
                "error",
                5000,
            )

        finally:
            if connection:
                connection.close()

    def set_combo_text(self, combo, text):
        index = combo.findText(
            str(text),
            Qt.MatchFlag.MatchFixedString,
        )

        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            combo.setCurrentText(str(text))

    # =========================================================
    # GET SELECTED USER
    # =========================================================

    def get_selected_user_id(self):
        if self.selected_user_id is None:
            self.show_toast(
                "Please select a user.",
                "warning",
            )
            return None

        return int(self.selected_user_id)

    def edit_selected_user(self):
        user_id = self.get_selected_user_id()

        if user_id is not None:
            self.open_user_for_edit(user_id)

    def edit_user_by_item(self, item):
        try:
            user_id = int(item)
        except (TypeError, ValueError):
            return

        self.open_user_for_edit(user_id)

    def delete_user_by_item(self, item):
        try:
            user_id = int(item)
        except (TypeError, ValueError):
            return

        self.delete_user_by_id(user_id)

    # =========================================================
    # DELETE USER
    # =========================================================

    def delete_user_by_id(self, user_id):
        self.selected_user_id = user_id
        self.select_user_row(user_id)

        connection = None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute("""
                SELECT Username
                FROM dbo.Users
                WHERE UserId = ?
                  AND IsActive = 1
            """, user_id)

            row = cursor.fetchone()

            if not row:
                self.show_toast(
                    "User not found.",
                    "warning",
                )
                return

            username = str(row[0] or "")

            # Admin cannot be deleted.
            if username.strip().lower() == "admin":
                self.show_toast(
                    "The Admin user cannot be deleted.",
                    "warning",
                )
                return

            answer = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Are you sure you want to delete '{username}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if answer != QMessageBox.StandardButton.Yes:
                return

            cursor.execute("""
                UPDATE dbo.Users
                SET IsActive = 0
                WHERE UserId = ?
            """, user_id)

            connection.commit()

            self.show_toast(
                "User deleted successfully.",
                "success",
            )

            if self.editing_user_id == user_id:
                self.reset_form()
            else:
                self.selected_user_id = None

            self.load_users()

        except Exception as error:

            if connection:
                try:
                    connection.rollback()
                except Exception:
                    pass

            print("Delete user error:", error)

            self.show_toast(
                str(error),
                "error",
                5000,
            )

        finally:
            if connection:
                connection.close()

    def delete_selected_user(self):
        user_id = self.get_selected_user_id()

        if user_id is not None:
            self.delete_user_by_id(user_id)

    # =========================================================
    # INSERT / UPDATE USER
    # =========================================================

    def save_user(self):

        username = self.username_entry.text().strip()
        password = self.password_entry.text().strip()
        user_type = self.user_type_combo.currentText().strip()
        department = self.department_combo.currentText().strip()

        # =====================================================
        # VALIDATION
        # =====================================================

        if not username:
            self.show_toast(
                "Please enter user name.",
                "warning",
            )
            self.username_entry.setFocus()
            return

        # Password required only for new user.
        if self.editing_user_id is None and not password:
            self.show_toast(
                "Please enter password.",
                "warning",
            )
            self.password_entry.setFocus()
            return

        invalid_user_types = {
            "",
            "Loading...",
            "Unable to load",
            "No User Type",
            "Select User Type",
        }

        if user_type in invalid_user_types:
            self.show_toast(
                "Please select User Type.",
                "warning",
            )
            return

        invalid_departments = {
            "",
            "Loading...",
            "Unable to load",
            "No Department",
            "Select Department",
        }

        if department in invalid_departments:
            self.show_toast(
                "Please select Department.",
                "warning",
            )
            return

        connection = None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            # =================================================
            # UPDATE EXISTING USER
            # =================================================

            if self.editing_user_id is not None:

                cursor.execute("""
                    SELECT COUNT(*)
                    FROM dbo.Users
                    WHERE Username = ?
                      AND UserId <> ?
                """,
                    username,
                    self.editing_user_id,
                )

                if cursor.fetchone()[0] > 0:
                    self.show_toast(
                        "Username already exists.",
                        "warning",
                    )
                    self.username_entry.setFocus()
                    return

                # Update password only when entered.
                if password:

                    password_hash = bcrypt.hashpw(
                        password.encode("utf-8"),
                        bcrypt.gensalt(),
                    ).decode("utf-8")

                    cursor.execute("""
                        UPDATE dbo.Users
                        SET
                            Username = ?,
                            PasswordHash = ?,
                            Role = ?,
                            DepartmentName = ?
                        WHERE UserId = ?
                    """,
                        username,
                        password_hash,
                        user_type,
                        department,
                        self.editing_user_id,
                    )

                else:

                    cursor.execute("""
                        UPDATE dbo.Users
                        SET
                            Username = ?,
                            Role = ?,
                            DepartmentName = ?
                        WHERE UserId = ?
                    """,
                        username,
                        user_type,
                        department,
                        self.editing_user_id,
                    )

                connection.commit()

                self.show_toast(
                    "User updated successfully.",
                    "success",
                )

                self.reset_form()
                self.load_users()
                return

            # =================================================
            # INSERT NEW USER
            # =================================================

            cursor.execute("""
                SELECT COUNT(*)
                FROM dbo.Users
                WHERE Username = ?
            """, username)

            if cursor.fetchone()[0] > 0:
                self.show_toast(
                    "Username already exists.",
                    "warning",
                )
                self.username_entry.setFocus()
                return

            password_hash = bcrypt.hashpw(
                password.encode("utf-8"),
                bcrypt.gensalt(),
            ).decode("utf-8")

            cursor.execute("""
                INSERT INTO dbo.Users
                (
                    Username,
                    PasswordHash,
                    Role,
                    DepartmentName,
                    IsActive,
                    CreatedDate
                )
                VALUES
                (
                    ?,
                    ?,
                    ?,
                    ?,
                    1,
                    GETDATE()
                )
            """,
                username,
                password_hash,
                user_type,
                department,
            )

            connection.commit()

            self.show_toast(
                "User created successfully.",
                "success",
            )

            self.reset_form()
            self.load_users()

        except Exception as error:

            if connection:
                try:
                    connection.rollback()
                except Exception:
                    pass

            print(
                "Save/update user error:",
                error,
            )

            self.show_toast(
                str(error),
                "error",
                5000,
            )

        finally:
            if connection:
                connection.close()

    # =========================================================
    # TOAST
    # =========================================================

    def show_toast(
        self,
        message,
        message_type="success",
        duration=3000,
    ):
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

        toast.move(
            root.width() - toast.width() - 15,
            20,
        )

        toast.raise_()
        toast.show()

        self._toast = toast

        def clear_reference():
            if self._toast is toast:
                self._toast = None

        QTimer.singleShot(
            duration + 100,
            clear_reference,
        )

        return toast

    # =========================================================
    # RESET
    # =========================================================

    def reset_form(self):

        self.editing_user_id = None
        self.selected_user_id = None

        self.username_entry.clear()
        self.password_entry.clear()
        self.password_entry.setPlaceholderText(
            "Enter password"
        )

        self.set_combo_text(
            self.user_type_combo,
            "Select User Type",
        )

        self.set_combo_text(
            self.department_combo,
            "Select Department",
        )

        self.save_button.setText("Save")
        self.table_widget.clearSelection()
        self.username_entry.setFocus()

    # =========================================================
    # BACK
    # =========================================================

    def go_back(self):
        if callable(self.back_callback):
            self.back_callback()


# =============================================================
# OPTIONAL STANDALONE TEST
# =============================================================

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = QMainWindow()
    window.setWindowTitle("HSI Automation Portal - User Master")
    window.resize(1347, 758)
    window.setMinimumSize(1100, 620)

    page = UserMasterPage(
        window,
        back_callback=window.close,
    )

    window.setCentralWidget(page)
    window.show()

    sys.exit(app.exec())
