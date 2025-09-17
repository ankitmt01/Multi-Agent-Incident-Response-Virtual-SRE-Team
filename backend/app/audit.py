
from __future__ import annotations
import os, json, time
from pathlib import Path
from typing import Any, Dict

AUDIT_FILE = Path(os.getenv("AUDIT_FILE", "state/logs/audit.log"))

def write_event(kind: str, payload: Dict[str, Any] | None = None) -> None:
    """Best-effort JSONL audit; never crash the app."""
    try:
        AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": time.time(), "kind": kind, "payload": payload or {}}
        with AUDIT_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
    
        pass
