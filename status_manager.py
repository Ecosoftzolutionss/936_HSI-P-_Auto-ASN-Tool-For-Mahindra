"""Central, thread-safe status hub and persistent activity log for HSI Mahindra Auto ASN."""
import re,sys,threading,time
from datetime import datetime
from pathlib import Path
from PyQt6.QtCore import QObject,pyqtSignal
MAX_HISTORY=500
LOG_DIR=Path(__file__).resolve().parent/"logs"
LOG_LOCK=threading.Lock()

def _safe(text):
    value=str(text)
    return re.sub(r"(?i)(otp|password|passwd|token)\s*[:=]\s*[^\s,|]+",r"\1=[hidden]",value)

def _write_activity_file(text,level):
    try:
        LOG_DIR.mkdir(parents=True,exist_ok=True)
        with LOG_LOCK:
            with (LOG_DIR/f"Mahindra_AutoASN_{datetime.now():%Y-%m-%d}.log").open("a",encoding="utf-8") as f: f.write(f"{text} [{level}]\n")
    except Exception: pass

class StatusHub(QObject):
    message=pyqtSignal(str,str)
    def __init__(self):
        super().__init__(); self.history=[]; self.error_count=0; self.last_activity=time.time(); self._lock=threading.Lock()
    def touch(self): self.last_activity=time.time()
    def publish(self,message,level="INFO",echo=True):
        level=str(level).upper(); text=f"[{datetime.now():%H:%M:%S}] {_safe(message)}"
        with self._lock:
            self.history.append((text,level)); del self.history[:-MAX_HISTORY]
            if level=="ERROR": self.error_count+=1
            self.last_activity=time.time()
        _write_activity_file(text,level)
        if echo and sys.__stdout__ is not None:
            try: sys.__stdout__.write(f"{text} [{level}]\n"); sys.__stdout__.flush()
            except Exception: pass
        try: self.message.emit(text,level)
        except Exception: pass
    def clear(self):
        with self._lock: self.history.clear(); self.error_count=0
_hub=None; _hub_lock=threading.Lock()
def get_hub():
    global _hub
    with _hub_lock:
        if _hub is None: _hub=StatusHub()
    return _hub
def get_log_dir(): LOG_DIR.mkdir(parents=True,exist_ok=True); return str(LOG_DIR)
def get_current_log_file(): LOG_DIR.mkdir(parents=True,exist_ok=True); return str(LOG_DIR/f"Mahindra_AutoASN_{datetime.now():%Y-%m-%d}.log")
def _base(path): return re.split(r"[\\/]",str(path).strip())[-1]
RULES=[
(re.compile(r"ASN CREATION DB UPDATE VERIFIED",re.I),lambda m:("ASN No and initial database status saved successfully.","SUCCESS")),
(re.compile(r"ASN BARCODE DOWNLOAD FAILED\s*(?:\|\s*REASON:\s*(.*))?",re.I),lambda m:("ASN Barcode download failed"+(f": {m.group(1)}" if m.group(1) else "."),"ERROR")),
(re.compile(r"ASN BARCODE DOWNLOAD STARTED",re.I),lambda m:("ASN Barcode PDF download started.","INFO")),
(re.compile(r"ASN BARCODE DOWNLOAD COMPLETED",re.I),lambda m:("ASN Barcode PDF downloaded successfully.","SUCCESS")),
(re.compile(r"AUTO_STATUS=1 VERIFIED for Invoice\s+(\S+)",re.I),lambda m:(f"Auto_Status=1 verified for invoice {m.group(1)}.","SUCCESS")),
(re.compile(r"AUTO_STATUS UPDATE FAILED for Invoice\s+(\S+)",re.I),lambda m:(f"Auto_Status update failed for invoice {m.group(1)}.","ERROR")),
(re.compile(r"INVOICE FAILED:\s*(\S+)\s*\|\s*REASON:\s*(.+)",re.I),lambda m:(f"Invoice {m.group(1)} failed: {m.group(2)}","ERROR")),
(re.compile(r"ALL PENDING ASN FILES PROCESSED|ALL PENDING ASN INVOICES ARE COMPLETED",re.I),lambda m:("All pending ASN work is complete.","SUCCESS")),
]
class ConsoleMirror:
    def __init__(self,stream,hub): self._stream=stream; self._hub=hub; self._local=threading.local(); self._last_text=None
    def write(self,data):
        data=data if isinstance(data,str) else str(data)
        if self._stream:
            try:self._stream.write(data)
            except Exception:pass
        buf=getattr(self._local,"buf","")+data
        if "\n" in buf:
            parts=buf.split("\n"); self._local.buf=parts[-1]
            for line in parts[:-1]: self._handle(line)
        else:self._local.buf=buf if len(buf)<10000 else ""
        return len(data)
    @staticmethod
    def _infer_level(line):
        u=line.upper()
        if any(x in u for x in ("ERROR","FAILED","FAILURE","EXCEPTION","NOT FOUND","COULD NOT","UNAVAILABLE")): return "ERROR"
        if any(x in u for x in ("WARNING","WARN","PARTIAL","SKIP","RETRY")): return "WARNING"
        if any(x in u for x in ("SUCCESS","COMPLETED","VERIFIED","PASSED")): return "SUCCESS"
        return "INFO"
    def _handle(self,line):
        line=_safe(line.strip())
        if not line:return
        self._hub.touch()
        for pattern,build in RULES:
            m=pattern.search(line)
            if m:
                text,level=build(m)
                if text!=self._last_text:self._last_text=text; self._hub.publish(text,level,echo=False)
                return
        if line!=self._last_text:self._last_text=line; self._hub.publish(line,self._infer_level(line),echo=False)
    def flush(self):
        if self._stream:
            try:self._stream.flush()
            except Exception:pass
    def isatty(self): return bool(self._stream and self._stream.isatty())
    @property
    def encoding(self): return getattr(self._stream,"encoding",None) or "utf-8"
    def __getattr__(self,name):
        if self._stream:return getattr(self._stream,name)
        raise AttributeError(name)
def install_console_mirror():
    hub=get_hub()
    if not isinstance(sys.stdout,ConsoleMirror):sys.stdout=ConsoleMirror(sys.stdout,hub)
    if not isinstance(sys.stderr,ConsoleMirror):sys.stderr=ConsoleMirror(sys.stderr,hub)
    return hub
