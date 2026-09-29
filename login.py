import bcrypt
from pathlib import Path

from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database import get_connection
from support_tool import SupportTool


class LoginWorker(QObject):
    success = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, username, password):
        super().__init__()
        self.username = username
        self.password = password

    def run(self):
        connection = None
        try:
            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute("""
                SELECT TOP 1
                    UserId,
                    Username,
                    PasswordHash,
                    Role,
                    ISNULL(DepartmentName, '') AS DepartmentName
                FROM dbo.Users
                WHERE Username = ?
                  AND IsActive = 1
            """, self.username)

            row = cursor.fetchone()

            if not row:
                self.failed.emit("Invalid username or password.")
                return

            db_username = str(row[1] or "").strip()
            db_role = str(row[3] or "").strip()

            # Application login is limited to users with the ADMIN role.
            if db_role.lower() != "admin":
                self.failed.emit(
                    "Only users with the Admin role are allowed to log in."
                )
                return

            stored_hash = str(row[2] or "").encode("utf-8")

            try:
                valid = bcrypt.checkpw(
                    self.password.encode("utf-8"),
                    stored_hash,
                )
            except Exception:
                valid = False

            if not valid:
                self.failed.emit("Invalid username or password.")
                return

            self.success.emit({
                "user_id": int(row[0]),
                "username": db_username,
                "role": db_role,
                "department": str(row[4] or ""),
            })

        except Exception as error:
            self.failed.emit(
                f"Unable to validate login: {error}"
            )

        finally:
            if connection:
                connection.close()

            self.finished.emit()


class LoginPage(QWidget):
    """
    HSI Mahindra Auto ASN - Login / Process Control.

    Left  : brand + ASN process control (Play works WITHOUT login)
    Right : Admin login card + live activity log
    """

    LEVELS = {
        "SUCCESS": ("\u2714", "#15803D"),
        "ERROR": ("\u2716", "#DC2626"),
        "WARNING": ("\u26A0", "#B45309"),
        "INFO": ("\u25CF", "#1D4ED8"),
    }

    # Survives logout so the log is not lost when the page is rebuilt.
    _history = []

    @staticmethod
    def _get_company_logo_path():
        """Find the HSI AUTO company logo without hard-coding one machine path."""
        base = Path(__file__).resolve().parent
        assets = base / "assets"

        preferred = [
            "HSI_AUTO_logo.png",
            "DashTopLogo.png",
            "Dashtoplogo.png",
            "Dashboardlogo.png",
            "Dashlogo.png",
            "HSIAUTO.png",
            "HSI_AUTO.png",
        ]

        for name in preferred:
            path = assets / name
            if path.is_file():
                return path

        # Fall back to any image whose filename contains "logo".
        if assets.is_dir():
            for path in sorted(assets.iterdir()):
                if (
                    path.is_file()
                    and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
                    and "logo" in path.stem.lower()
                ):
                    return path

        return None

    @classmethod
    def _logo_label(cls, max_width=170, max_height=58, dark=False):
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setMinimumHeight(max_height)

        path = cls._get_company_logo_path()
        if path:
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    max_width,
                    max_height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                label.setPixmap(scaled)
                return label

        label.setText("HSI AUTO")
        label.setStyleSheet(
            "color:white; font-size:22px; font-weight:800;"
            if dark
            else "color:#123A7A; font-size:22px; font-weight:800;"
        )
        return label

    STYLE = """
        QWidget { font-family: "Segoe UI"; color: #10182D; }
        QLabel { background: transparent; border: none; }

        #brandPanel {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #1A63F2, stop:1 #0A2E8C);
        }
        #controlCard {
            background: rgba(255,255,255,0.12);
            border: 1px solid rgba(255,255,255,0.28);
            border-radius: 14px;
        }
        #rightPanel { background: #EEF1FA; }
        #loginCard, #activityCard {
            background: #FFFFFF;
            border: 1px solid #DCE4F2;
            border-radius: 16px;
        }

        QLineEdit {
            background: #F8FAFD; color: #10182D;
            border: 1px solid #D5DBE7; border-radius: 8px;
            padding: 0 12px; font-size: 13px; min-height: 42px;
        }
        QLineEdit:focus { border: 1.5px solid #2E6DEB; background: #FFFFFF; }

        #loginBtn {
            background: #1457E6; color: white; border: none;
            border-radius: 8px; font-size: 13px; font-weight: 600;
        }
        #loginBtn:hover { background: #0E48C7; }
        #loginBtn:disabled { background: #A8B7D8; }

        #playBtn {
            background: #16A34A; color: white; border: none;
            border-radius: 10px; font-size: 14px; font-weight: 700;
        }
        #playBtn:hover { background: #12833C; }
        #playBtn:disabled { background: rgba(255,255,255,0.28); color: #E5EDFF; }

        #supportBtn {
            background: transparent; color: white;
            border: 1px solid rgba(255,255,255,0.55);
            border-radius: 10px; font-size: 12px; font-weight: 600;
        }
        #supportBtn:hover { background: rgba(255,255,255,0.15); }

        #eyeBtn { background: transparent; border: none; font-size: 14px; color: #71809E; }
        #eyeBtn:hover { color: #1457E6; }

        #clearBtn {
            background: transparent; color: #71809E; border: none;
            font-size: 11px; padding: 2px 6px;
        }
        #clearBtn:hover { color: #1457E6; }

        #errorLabel {
            color: #B91C1C; background: #FEF2F2;
            border: 1px solid #FECACA; border-radius: 6px;
            padding: 6px 10px; font-size: 11px;
        }

        QListWidget {
            background: transparent; border: none; outline: none;
            font-family: Consolas, "Segoe UI"; font-size: 11px;
        }
        QListWidget::item { padding: 3px 2px; }
        QScrollBar:vertical { width: 8px; background: transparent; }
        QScrollBar::handle:vertical { background: #CBD5E1; border-radius: 4px; min-height: 24px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    """

    def __init__(
        self,
        master=None,
        login_success=None,
        automation_service=None,
        support_callback=None,
    ):
        super().__init__(master)

        self.login_success = login_success
        self.automation_service = automation_service
        self.support_callback = support_callback
        self.login_thread = None
        self.login_worker = None
        self.support_tool = None

        self.setStyleSheet(self.STYLE)
        self.create_ui()

        for message, level in LoginPage._history:
            self._append_status(message, level)

        if self.automation_service is not None:
            self.automation_service.status.connect(self.add_status)
            self.automation_service.running_changed.connect(self.update_play_button)
            self.update_play_button(self.automation_service.is_running)
        else:
            self.update_play_button(False)

    def showEvent(self, event):
        super().showEvent(event)
        if self.username.text().strip():
            self.password.setFocus()
        else:
            self.username.setFocus()

    # =========================================================
    # UI
    # =========================================================

    def create_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_brand_panel(), 4)
        root.addWidget(self._build_right_panel(), 6)

    def _build_brand_panel(self):
        panel = QFrame()
        panel.setObjectName("brandPanel")
        panel.setMinimumWidth(400)

        lay = QVBoxLayout(panel)
        lay.setContentsMargins(42, 34, 42, 28)
        lay.setSpacing(0)

        # Company logo
        logo_wrap = QFrame()
        logo_wrap.setStyleSheet(
            "QFrame { background:#FFFFFF; border:1px solid rgba(255,255,255,0.35); "
            "border-radius:12px; }"
        )
        logo_lay = QHBoxLayout(logo_wrap)
        logo_lay.setContentsMargins(12, 8, 12, 8)
        logo_lay.addWidget(self._logo_label(185, 54))
        lay.addWidget(logo_wrap, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addSpacing(24)

        badge = QLabel("ASN AUTOMATION")
        badge.setStyleSheet(
            "color:#DCE6FF; font-size:11px; font-weight:700; letter-spacing:2px;"
        )
        lay.addWidget(badge)
        lay.addSpacing(8)

        title = QLabel("HSI Mahindra\nAuto ASN")
        title.setStyleSheet("color:white; font-size:34px; font-weight:800;")
        lay.addWidget(title)
        lay.addSpacing(12)

        tagline = QLabel(
            "Automated Advance Shipping Notice preparation "
            "and Mahindra Supplier Portal submission."
        )
        tagline.setWordWrap(True)
        tagline.setStyleSheet("color:#DCE6FF; font-size:13px;")
        lay.addWidget(tagline)

        lay.addStretch(1)

        # ---- process control card ----
        card = QFrame()
        card.setObjectName("controlCard")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(22, 20, 22, 22)
        cl.setSpacing(0)

        head = QHBoxLayout()
        head_title = QLabel("ASN Process")
        head_title.setStyleSheet("color:white; font-size:16px; font-weight:700;")
        head.addWidget(head_title)
        head.addStretch()
        self.status_chip = QLabel()
        head.addWidget(self.status_chip)
        cl.addLayout(head)
        cl.addSpacing(4)

        hint = QLabel("Runs in the background. No login required.")
        hint.setStyleSheet("color:#DCE6FF; font-size:11px;")
        cl.addWidget(hint)
        cl.addSpacing(16)

        self.play_btn = QPushButton("\u25B6   Start ASN Process")
        self.play_btn.setObjectName("playBtn")
        self.play_btn.setFixedHeight(48)
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.setToolTip("Start the ASN process without logging in")
        self.play_btn.clicked.connect(self.play_process)
        cl.addWidget(self.play_btn)
        cl.addSpacing(10)

        self.support_btn = QPushButton("\U0001F6E0   Support Tool  (restart if stuck)")
        self.support_btn.setObjectName("supportBtn")
        self.support_btn.setFixedHeight(40)
        self.support_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.support_btn.clicked.connect(self.open_support_tool)
        cl.addWidget(self.support_btn)

        lay.addWidget(card)
        lay.addSpacing(24)

        footer = QLabel("\u00A9 2026 HSI Mahindra Auto ASN. All rights reserved.")
        footer.setStyleSheet("color:#B7C8F5; font-size:10px;")
        lay.addWidget(footer)
        return panel

    def _build_right_panel(self):
        panel = QFrame()
        panel.setObjectName("rightPanel")

        lay = QVBoxLayout(panel)
        lay.setContentsMargins(42, 28, 42, 22)
        lay.setSpacing(16)

        # ---- login card, centred ----
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self._build_login_card())
        row.addStretch(1)
        lay.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)

        lay.addWidget(self._build_activity_card())
        return panel

    def _build_login_card(self):
        card = QFrame()
        card.setObjectName("loginCard")
        card.setFixedWidth(410)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(34, 26, 34, 28)
        lay.setSpacing(0)

        logo = self._logo_label(155, 48)
        logo.setStyleSheet(
            "background:#F8FAFD; border:1px solid #E5EAF3; "
            "border-radius:10px; padding:5px;"
        )
        lay.addWidget(logo, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(16)

        title = QLabel("Admin Login")
        title.setStyleSheet("font-size:24px; font-weight:700;")
        lay.addWidget(title)
        lay.addSpacing(2)

        sub = QLabel("Sign in with an Admin account to manage configuration.")
        sub.setStyleSheet("color:#71809E; font-size:12px;")
        lay.addWidget(sub)
        lay.addSpacing(18)

        lay.addWidget(self._field_label("Username"))
        lay.addSpacing(5)
        self.username = QLineEdit()
        self.username.setPlaceholderText("Enter username")
        lay.addWidget(self.username)
        lay.addSpacing(12)

        lay.addWidget(self._field_label("Password"))
        lay.addSpacing(5)
        self.password = QLineEdit()
        self.password.setPlaceholderText("Enter password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setStyleSheet("QLineEdit { padding-right: 38px; }")

        eye_layout = QHBoxLayout(self.password)
        eye_layout.setContentsMargins(0, 0, 6, 0)
        eye_layout.addStretch()
        self.eye_btn = QPushButton("\U0001F441")
        self.eye_btn.setObjectName("eyeBtn")
        self.eye_btn.setFixedSize(28, 28)
        self.eye_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.eye_btn.setToolTip("Show / hide password")
        self.eye_btn.clicked.connect(self.toggle_password)
        eye_layout.addWidget(self.eye_btn)
        lay.addWidget(self.password)
        lay.addSpacing(10)

        self.error_label = QLabel()
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        lay.addWidget(self.error_label)
        lay.addSpacing(8)

        self.login_btn = QPushButton("Login")
        self.login_btn.setObjectName("loginBtn")
        self.login_btn.setFixedHeight(44)
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.clicked.connect(self.login)
        lay.addWidget(self.login_btn)

        self.username.returnPressed.connect(self.password.setFocus)
        self.password.returnPressed.connect(self.login)
        self.username.textChanged.connect(self.clear_error)
        self.password.textChanged.connect(self.clear_error)
        return card

    def _build_activity_card(self):
        card = QFrame()
        card.setObjectName("activityCard")
        card.setFixedHeight(180)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 12, 12, 10)
        lay.setSpacing(4)

        head = QHBoxLayout()
        t = QLabel("Live Activity")
        t.setStyleSheet("font-size:14px; font-weight:700;")
        head.addWidget(t)
        self.count_label = QLabel("0 events")
        self.count_label.setStyleSheet("color:#94A3B8; font-size:11px;")
        head.addWidget(self.count_label)
        head.addStretch()
        clear = QPushButton("Clear")
        clear.setObjectName("clearBtn")
        clear.setCursor(Qt.CursorShape.PointingHandCursor)
        clear.clicked.connect(self.clear_status)
        head.addWidget(clear)
        lay.addLayout(head)

        self.status_list = QListWidget()
        self.status_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.status_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        lay.addWidget(self.status_list, 1)

        self.empty_hint = "Waiting for activity \u2014 login, process and error events appear here."
        self._show_empty_hint()
        return card

    @staticmethod
    def _field_label(text):
        label = QLabel(text)
        label.setStyleSheet("font-size:12px; font-weight:600; color:#374151;")
        return label

    # =========================================================
    # STATUS LOG
    # =========================================================

    def _show_empty_hint(self):
        if self.status_list.count() == 0:
            item = QListWidgetItem(self.empty_hint)
            item.setForeground(QColor("#94A3B8"))
            item.setData(Qt.ItemDataRole.UserRole, "hint")
            self.status_list.addItem(item)

    def _append_status(self, message, level):
        if (
            self.status_list.count() == 1
            and self.status_list.item(0).data(Qt.ItemDataRole.UserRole) == "hint"
        ):
            self.status_list.clear()

        icon, color = self.LEVELS.get(level, self.LEVELS["INFO"])
        item = QListWidgetItem(f"{icon}  {message}")
        item.setForeground(QColor(color))
        self.status_list.addItem(item)

        while self.status_list.count() > 500:
            self.status_list.takeItem(0)

        self.status_list.scrollToBottom()
        self.count_label.setText(f"{self.status_list.count()} events")

    def add_status(self, message, level="INFO"):
        level = str(level).upper()
        LoginPage._history.append((message, level))
        del LoginPage._history[:-500]
        self._append_status(message, level)

    def clear_status(self):
        LoginPage._history.clear()
        self.status_list.clear()
        self.count_label.setText("0 events")
        self._show_empty_hint()

    # =========================================================
    # PROCESS CONTROL
    # =========================================================

    def update_play_button(self, running):
        self.play_btn.setEnabled(not running)
        self.play_btn.setText(
            "\u23F3   Process Running\u2026" if running else "\u25B6   Start ASN Process"
        )
        if running:
            self.status_chip.setText("\u25CF Running")
            self.status_chip.setStyleSheet(
                "background:rgba(34,197,94,0.30); color:#BBF7D0; "
                "border-radius:10px; padding:3px 10px; font-size:11px; font-weight:700;"
            )
        else:
            self.status_chip.setText("\u25CF Idle")
            self.status_chip.setStyleSheet(
                "background:rgba(255,255,255,0.18); color:#DCE6FF; "
                "border-radius:10px; padding:3px 10px; font-size:11px; font-weight:700;"
            )

    def play_process(self):
        if self.automation_service is None:
            self.add_status("Automation service is unavailable.", "ERROR")
            return

        if self.automation_service.start("Login Page - Play"):
            self.add_status("Play request accepted.", "SUCCESS")

    def open_support_tool(self):
        # Let the main window own the Support Tool when a callback is supplied.
        # This avoids creating a second SupportTool instance from LoginPage.
        if callable(self.support_callback):
            self.support_callback()
            return

        # Backward-compatible fallback for running LoginPage by itself.
        if self.automation_service is None:
            return

        if self.support_tool is None:
            self.support_tool = SupportTool(
                self.automation_service,
                parent=self.window(),
            )

        self.support_tool.show()
        self.support_tool.raise_()
        self.support_tool.activateWindow()

    # =========================================================
    # LOGIN
    # =========================================================

    def toggle_password(self):
        hidden = self.password.echoMode() == QLineEdit.EchoMode.Password
        self.password.setEchoMode(
            QLineEdit.EchoMode.Normal if hidden else QLineEdit.EchoMode.Password
        )
        self.eye_btn.setText("\U0001F576" if hidden else "\U0001F441")

    def show_error(self, message):
        self.error_label.setText(message)
        self.error_label.show()

    def clear_error(self, *_):
        if self.error_label.isVisible():
            self.error_label.hide()

    def login(self):
        if self.login_thread is not None:
            return  # already signing in

        username = self.username.text().strip()
        password = self.password.text()

        if not username:
            self.show_error("Please enter your username.")
            self.username.setFocus()
            return

        if not password:
            self.show_error("Please enter your password.")
            self.password.setFocus()
            return

        self.clear_error()
        self.login_btn.setEnabled(False)
        self.login_btn.setText("Signing in\u2026")
        self.add_status("Validating credentials.", "INFO")

        self.login_thread = QThread()
        self.login_worker = LoginWorker(username, password)
        self.login_worker.moveToThread(self.login_thread)

        self.login_thread.started.connect(self.login_worker.run)
        self.login_worker.success.connect(self.on_login_success)
        self.login_worker.failed.connect(self.on_login_failed)
        self.login_worker.finished.connect(self.login_thread.quit)
        self.login_worker.finished.connect(self.login_worker.deleteLater)
        self.login_thread.finished.connect(self.login_thread.deleteLater)
        self.login_thread.finished.connect(self.on_login_thread_finished)

        self.login_thread.start()

    def on_login_success(self, user):
        name = user.get("username", "Admin") if isinstance(user, dict) else "Admin"
        self.add_status(f"User login successful - {name}.", "SUCCESS")

        if callable(self.login_success):
            self.login_success(user)

    def on_login_failed(self, message):
        self.add_status(message, "ERROR")
        self.show_error(message)
        self.password.selectAll()
        self.password.setFocus()

    def on_login_thread_finished(self):
        self.login_thread = None
        self.login_worker = None
        self.login_btn.setEnabled(True)
        self.login_btn.setText("Login")
