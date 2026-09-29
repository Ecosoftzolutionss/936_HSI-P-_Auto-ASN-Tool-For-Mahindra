from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QFrame,QLabel,QPushButton,QStackedWidget
from user_master import UserMasterPage
from settings import SettingsPage
from support_tool import SupportTool
STYLE='''QWidget{font-family:"Segoe UI";color:#10182D;}#root{background:#F5F7FB;}#side{background:#0F3D8F;}#side QLabel{color:white;}#nav QPushButton{background:transparent;color:#DCE7FF;border:none;text-align:left;padding:12px 16px;border-radius:8px;font-weight:600;}#nav QPushButton:hover,#nav QPushButton:checked{background:#1E5CCB;color:white;}#content{background:#F5F7FB;}#top{background:white;border-bottom:1px solid #E2E8F0;}#card{background:white;border:1px solid #E2E8F0;border-radius:14px;}QPushButton{background:white;border:1px solid #D6DCE8;border-radius:8px;min-height:36px;padding:0 14px;font-weight:600;}#primary{background:#1457E6;color:white;border:none;}'''
class DashboardPage(QWidget):
    def __init__(self,master=None,user=None,logout_callback=None,automation_service=None,excel_service=None):
        super().__init__(master); self.user=user or {}; self.logout_callback=logout_callback; self.service=automation_service; self.excel=excel_service; self.setStyleSheet(STYLE); self.support=None; self._build()
    def _build(self):
        root=QHBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        side=QFrame(); side.setObjectName('side'); side.setFixedWidth(220); sl=QVBoxLayout(side); sl.setContentsMargins(16,24,16,16); title=QLabel('HSI Mahindra\nAuto ASN'); title.setStyleSheet('font-size:20px;font-weight:800;'); sl.addWidget(title); sl.addSpacing(20); nav=QVBoxLayout(); nav.setObjectName('nav'); self.stack=QStackedWidget();
        self.home=self._home(); self.user_page=UserMasterPage(self,back_callback=lambda:self.stack.setCurrentWidget(self.home)); self.config_page=SettingsPage(self,back_callback=lambda:self.stack.setCurrentWidget(self.home)); navitems=[('▣  Dashboard',self.home),('👥  User Master',self.user_page),('⚙  Configuration',self.config_page)]
        for text,page in navitems:
            b=QPushButton(text); b.setCheckable(True); b.clicked.connect(lambda checked,p=page:self._select(p)); nav.addWidget(b)
            if page is self.home:self.home_btn=b
        nav.addStretch(); support=QPushButton('🛠  Support Tool'); support.clicked.connect(self.open_support); nav.addWidget(support); logout=QPushButton('↪  Logout'); logout.clicked.connect(self.logout); nav.addWidget(logout); sl.addLayout(nav); root.addWidget(side)
        content=QFrame(); content.setObjectName('content'); cl=QVBoxLayout(content); cl.setContentsMargins(0,0,0,0); top=QFrame(); top.setObjectName('top'); top.setFixedHeight(68); tl=QHBoxLayout(top); tl.setContentsMargins(24,0,24,0); head=QLabel('Dashboard'); head.setStyleSheet('font-size:18px;font-weight:800;'); tl.addWidget(head); tl.addStretch(); tl.addWidget(QLabel(f"Admin: {self.user.get('username','Admin')}")); cl.addWidget(top); cl.addWidget(self.stack,1); self.stack.addWidget(self.home); self.stack.addWidget(self.user_page); self.stack.addWidget(self.config_page); root.addWidget(content,1); self._select(self.home)
    def _home(self):
        w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(28,26,28,26); title=QLabel('ASN Process Control'); title.setStyleSheet('font-size:26px;font-weight:800;'); l.addWidget(title); l.addWidget(QLabel('The automation runs in Microsoft Edge in the background.')); row=QHBoxLayout();
        for t,v in [('ASN Automation','Runs in background'),('Excel Queue','Prepared every 20 minutes'),('Negative Handling','Invoice-level status')]:
            c=QFrame(); c.setObjectName('card'); x=QVBoxLayout(c); a=QLabel(t); a.setStyleSheet('font-size:15px;font-weight:700;'); x.addWidget(a); x.addWidget(QLabel(v)); row.addWidget(c)
        l.addLayout(row); l.addStretch(); return w
    def _select(self,page):
        self.stack.setCurrentWidget(page)
    def open_support(self):
        if not self.support:self.support=SupportTool(self.service,self.excel,self.window())
        self.support.show(); self.support.raise_(); self.support.activateWindow()
    def logout(self):
        if callable(self.logout_callback):self.logout_callback()
