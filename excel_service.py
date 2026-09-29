import threading,time
from PyQt6.QtCore import QObject,pyqtSignal
from status_manager import get_hub
class ExcelPreparationService(QObject):
    status=pyqtSignal(str,str); running_changed=pyqtSignal(bool)
    def __init__(self):
        super().__init__(); self.hub=get_hub(); self.hub.message.connect(self.status); self._running=False; self._stop=threading.Event(); self._thread=None; self.interval=20*60
    @property
    def history(self):return self.hub.history
    @property
    def is_running(self):return self._running
    def publish(self,m,l='INFO'):self.hub.publish(m,l)
    def start(self):
        if self._running:return False
        self._stop.clear(); self._running=True; self.running_changed.emit(True); self._thread=threading.Thread(target=self._loop,daemon=True,name='ASNExcelScheduler'); self._thread.start(); return True
    def _cycle(self):
        try:
            import excelprepare
            excelprepare.prepare_new_asn_file()
        except Exception as e:self.publish(f'ASN preparation cycle failed: {e}','ERROR')
    def _loop(self):
        self.publish('ASN Excel preparation scheduler started.','SUCCESS'); self._cycle()
        while not self._stop.wait(self.interval):self._cycle()
        self._running=False; self.running_changed.emit(False); self.publish('ASN Excel preparation scheduler stopped.','WARNING')
    def run_now(self):threading.Thread(target=self._cycle,daemon=True,name='ASNExcelRunNow').start()
    def restart(self):
        self.stop(); time.sleep(.5); self.start()
    def stop(self):self._stop.set()
