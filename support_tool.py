import os,sys,subprocess
from PyQt6.QtCore import Qt,pyqtSignal
from PyQt6.QtGui import QColor,QGuiApplication
from PyQt6.QtWidgets import QFrame,QHBoxLayout,QLabel,QListWidget,QListWidgetItem,QMessageBox,QPushButton,QVBoxLayout,QWidget
from status_manager import get_current_log_file,get_log_dir
LEVELS={"SUCCESS":("✔","#15803D"),"ERROR":("✖","#DC2626"),"WARNING":("⚠","#B45309"),"INFO":("●","#1D4ED8")}
class StatusLog(QListWidget):
    count_changed=pyqtSignal(int); HINT="Waiting for activity — login, process and error events appear here."
    def __init__(self,parent=None):
        super().__init__(parent); self.setSelectionMode(QListWidget.SelectionMode.NoSelection); self.setFocusPolicy(Qt.FocusPolicy.NoFocus); self.setWordWrap(True); self._show_hint()
    def _show_hint(self):
        if self.count()==0:
            i=QListWidgetItem(self.HINT); i.setForeground(QColor("#94A3B8")); i.setData(Qt.ItemDataRole.UserRole,"hint"); self.addItem(i)
    def _has_hint(self): return self.count()==1 and self.item(0).data(Qt.ItemDataRole.UserRole)=="hint"
    def add_message(self,message,level="INFO"):
        if self._has_hint():self.clear()
        icon,color=LEVELS.get(str(level).upper(),LEVELS["INFO"]); i=QListWidgetItem(f"{icon}  {message}"); i.setForeground(QColor(color)); self.addItem(i)
        while self.count()>500:self.takeItem(0)
        self.scrollToBottom(); self.count_changed.emit(self.count())
    def replay(self,history):
        for message,level in list(history):self.add_message(message,level)
    def clear_log(self):self.clear(); self._show_hint(); self.count_changed.emit(0)
    def plain_text(self):return "" if self._has_hint() else "\n".join(self.item(i).text() for i in range(self.count()))
STYLE="""
QWidget{font-family:"Segoe UI";color:#10182D;}
#root{background:#F5F7FB;}
#card{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:14px;}
QPushButton{background:#FFFFFF;border:1px solid #D6DCE8;border-radius:8px;min-height:36px;padding:0 14px;font-weight:600;}
QPushButton:hover{background:#F5F7FB;}
#primary{background:#2563EB;color:white;border:none;}
#danger{color:#B91C1C;border-color:#FECACA;}
#logPath{color:#64748B;font-size:11px;}
QListWidget{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:10px;padding:6px;font-family:Consolas,"Segoe UI";font-size:11px;}
"""
class SupportTool(QWidget):
    def __init__(self,automation_service,excel_service=None,parent=None):
        if excel_service is not None and not self._looks_like_excel_service(excel_service):
            if parent is None:parent=excel_service
            excel_service=None
        super().__init__(parent,Qt.WindowType.Window); self.service=automation_service; self.excel=excel_service
        self.setWindowTitle("HSI Mahindra Auto ASN - Support Tool"); self.resize(950,720); self.setMinimumSize(800,600); self.setObjectName("root"); self.setStyleSheet(STYLE); self._build_ui()
        try:self.log.replay(self.service.history)
        except Exception:pass
        try:self.service.status.connect(self.log.add_message)
        except Exception:pass
        try:self.service.running_changed.connect(self._update_process_state)
        except Exception:pass
        self._update_process_state(bool(getattr(self.service,"is_running",False)))
        if self.excel is not None:
            try:self.excel.status.connect(self.log.add_message)
            except Exception:pass
            try:self.excel.running_changed.connect(self._update_excel_state)
            except Exception:pass
            self._update_excel_state(bool(getattr(self.excel,"is_running",False)))
    @staticmethod
    def _looks_like_excel_service(value):return all(hasattr(value,name) for name in ("run_now","restart"))
    def _card(self,title):
        card=QFrame(); card.setObjectName("card"); layout=QVBoxLayout(card); layout.setContentsMargins(16,14,16,16); layout.setSpacing(10); head=QHBoxLayout(); label=QLabel(title); label.setStyleSheet("font-size:14px;font-weight:700;"); head.addWidget(label); head.addStretch(); chip=QLabel(); head.addWidget(chip); layout.addLayout(head); return card,layout,chip
    def _button(self,text,callback,object_name=None):
        b=QPushButton(text); b.setCursor(Qt.CursorShape.PointingHandCursor); b.setObjectName(object_name or ""); b.clicked.connect(callback); return b
    def _build_ui(self):
        root=QVBoxLayout(self); root.setContentsMargins(22,20,22,20); root.setSpacing(12); title=QLabel("Support Tool"); title.setStyleSheet("font-size:24px;font-weight:800;"); root.addWidget(title); hint=QLabel("Recovery, diagnostics and activity history. The log is also saved automatically to a daily file."); hint.setStyleSheet("color:#64748B;font-size:12px;"); root.addWidget(hint)
        cards=QHBoxLayout(); cards.setSpacing(12); card,layout,self.process_chip=self._card("ASN Process"); buttons=QHBoxLayout(); self.start_btn=self._button("▶  Start",lambda:self._safe_call(getattr(self.service,"start",None),"Support Tool - Start"),"primary"); self.restart_btn=self._button("↻  Restart",self._restart); self.stop_btn=self._button("■  Stop",self._stop,"danger"); buttons.addWidget(self.start_btn); buttons.addWidget(self.restart_btn); buttons.addWidget(self.stop_btn); layout.addLayout(buttons); cards.addWidget(card,3)
        if self.excel is not None:
            card,layout,self.excel_chip=self._card("Excel Preparation"); buttons=QHBoxLayout(); buttons.addWidget(self._button("Run Now",self._excel_run_now)); buttons.addWidget(self._button("Restart",self._excel_restart)); layout.addLayout(buttons); cards.addWidget(card,2)
        root.addLayout(cards); actions=QHBoxLayout(); actions.addWidget(self._button("Run Pre-checks",self._run_prechecks)); actions.addWidget(self._button("Test Database",self._test_database)); actions.addWidget(self._button("Open Logs",self._open_logs)); actions.addWidget(self._button("Copy Log",self._copy_log)); actions.addWidget(self._button("Clear Screen",self._clear_log)); root.addLayout(actions)
        self.log_path=QLabel(f"Activity file: {get_current_log_file()}"); self.log_path.setObjectName("logPath"); root.addWidget(self.log_path); activity_title=QLabel("Live Activity"); activity_title.setStyleSheet("font-size:14px;font-weight:700;"); root.addWidget(activity_title); self.log=StatusLog(); root.addWidget(self.log,1)
    @staticmethod
    def _safe_call(fn,*args):
        if callable(fn):
            try:return fn(*args)
            except TypeError:return fn()
            except Exception:return None
        return None
    def _excel_run_now(self):self._safe_call(getattr(self.excel,"run_now",None))
    def _excel_restart(self):self._safe_call(getattr(self.excel,"restart",None))
    def _run_prechecks(self):self._safe_call(getattr(self.service,"run_prechecks",None))
    def _test_database(self):self._safe_call(getattr(self.service,"test_database",None))
    def _open_logs(self):
        folder=get_log_dir()
        try:
            if os.name=="nt":os.startfile(folder)
            elif sys.platform=="darwin":subprocess.Popen(["open",folder])
            else:subprocess.Popen(["xdg-open",folder])
        except Exception as error:QMessageBox.warning(self,"Logs",f"Could not open log folder.\n\n{folder}\n\n{error}")
    @staticmethod
    def _set_chip(label,running,on_text,off_text):
        label.setText("● "+(on_text if running else off_text)); label.setStyleSheet(("color:#166534;background:#DCFCE7;" if running else "color:#475569;background:#E2E8F0;")+"border-radius:9px;padding:3px 10px;font-weight:700;")
    def _update_process_state(self,running):self.start_btn.setEnabled(not running); self.stop_btn.setEnabled(running); self._set_chip(self.process_chip,running,"Running","Idle")
    def _update_excel_state(self,running):
        if hasattr(self,"excel_chip"):self._set_chip(self.excel_chip,running,"Scheduler on","Scheduler off")
    def _restart(self):
        if not bool(getattr(self.service,"is_running",False)):self._safe_call(getattr(self.service,"restart",None)); return
        if QMessageBox.question(self,"Restart","Stop the current run and restart Edge?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:self._safe_call(getattr(self.service,"restart",None))
    def _stop(self):
        if QMessageBox.question(self,"Stop","Stop the ASN process and close only the automation Edge window?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:self._safe_call(getattr(self.service,"stop_async",None))
    def _copy_log(self):
        QGuiApplication.clipboard().setText(self.log.plain_text()); publish=getattr(self.service,"publish",None)
        if callable(publish):publish("Current activity log copied to clipboard.","INFO")
    def _clear_log(self):
        hub=getattr(self.service,"hub",None)
        if hub is not None:
            try:hub.clear()
            except Exception:pass
        self.log.clear_log(); self.log_path.setText(f"Activity file: {get_current_log_file()} (disk history is kept)")
    def closeEvent(self,event):event.accept()
