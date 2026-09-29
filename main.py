import sys
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication,QMainWindow,QStackedWidget
from status_manager import install_console_mirror,get_hub
from automation_service import AutomationService
from excel_service import ExcelPreparationService
from login import LoginPage
from dashboard import DashboardPage
class HSIApplication(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('HSI Mahindra Auto ASN'); self.resize(1280,800); self.setMinimumSize(1050,700)
        self.service=AutomationService(self); self.excel=ExcelPreparationService(); self.stack=QStackedWidget(); self.setCentralWidget(self.stack); self.login_page=None; self.dashboard=None; self.show_login(); self.excel.start(); get_hub().publish('HSI Mahindra Auto ASN is ready.','SUCCESS')
    def show_login(self):
        self.login_page=LoginPage(self,login_success=self.on_login,automation_service=self.service); self.stack.addWidget(self.login_page); self.stack.setCurrentWidget(self.login_page)
    def on_login(self,user):
        self.dashboard=DashboardPage(self,user=user,logout_callback=self.logout,automation_service=self.service,excel_service=self.excel); self.stack.addWidget(self.dashboard); self.stack.setCurrentWidget(self.dashboard)
    def logout(self):
        if self.dashboard:self.dashboard.deleteLater(); self.dashboard=None
        self.show_login()
    def closeEvent(self,event):
        try:self.service.close()
        except Exception:pass
        try:self.excel.stop()
        except Exception:pass
        event.accept()
def main():
    app=QApplication(sys.argv); app.setApplicationName('HSI Mahindra Auto ASN'); install_console_mirror(); w=HSIApplication(); w.show(); return app.exec()
if __name__=='__main__':raise SystemExit(main())
