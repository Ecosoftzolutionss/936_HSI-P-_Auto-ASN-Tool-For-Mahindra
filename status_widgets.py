from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QListWidget, QListWidgetItem
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
