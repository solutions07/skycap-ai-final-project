import json, sys, time, uuid, os
from datetime import datetime

LOG_LEVELS = {"DEBUG":10, "INFO":20, "WARN":30, "ERROR":40}
CURRENT_LEVEL = LOG_LEVELS.get(os.getenv("SKYCAP_LOG_LEVEL","INFO").upper(), 20)

def _emit(record: dict):
    try:
        sys.stdout.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        sys.stdout.write(str(record) + "\n")
    sys.stdout.flush()

_def_app = os.getenv("SKYCAP_APP","skycap-ai")

def log_event(event: str, level: str = "INFO", **fields):
    if LOG_LEVELS.get(level, 100) < CURRENT_LEVEL:
        return
    rec = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "event": event,
        "app": _def_app,
        "fields": fields,
    }
    _emit(rec)

# Convenience wrappers

def log_debug(event: str, **fields):
    log_event(event, "DEBUG", **fields)

def log_info(event: str, **fields):
    log_event(event, "INFO", **fields)

def log_warn(event: str, **fields):
    log_event(event, "WARN", **fields)

def log_error(event: str, **fields):
    log_event(event, "ERROR", **fields)

class QueryTimer:
    """Context manager for timing query lifecycle segments."""
    def __init__(self, phase: str, **meta):
        self.phase = phase
        self.meta = meta
        self.start = None
    def __enter__(self):
        self.start = time.time()
        return self
    def __exit__(self, exc_type, exc, tb):
        dur = time.time() - self.start if self.start else None
        if exc:
            log_error("phase_error", phase=self.phase, duration=dur, error=str(exc), **self.meta)
        else:
            log_debug("phase_complete", phase=self.phase, duration=dur, **self.meta)
