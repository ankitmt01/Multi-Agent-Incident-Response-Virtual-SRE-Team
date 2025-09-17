from __future__ import annotations
import json, uuid
import datetime as dt
from pathlib import Path
from typing import Any, Dict
from .config import STATE_DIR as _STATE_DIR

# in-memory state
INCIDENTS: Dict[str, Any] = {}
RESULTS: Dict[str, Any] = {}
APPROVALS: Dict[str, bool] = {}

# files
STATE_DIR = Path(_STATE_DIR)
STATE_DIR.mkdir(parents=True, exist_ok=True)
STATE_INCIDENTS = STATE_DIR / "incidents.json"
STATE_RESULTS   = STATE_DIR / "results.json"
STATE_APPROVALS = STATE_DIR / "approvals.json"

def _json_default(o: Any) -> Any:
    # pydantic v2/v1 support
    try:
        from pydantic import BaseModel as _PydBase  # type: ignore
        if isinstance(o, _PydBase):
            if hasattr(o, "model_dump"):
                return o.model_dump()
            if hasattr(o, "dict"):
                return o.dict()
    except Exception:
        pass
    if isinstance(o, (dt.datetime, dt.date, dt.time)):
        return o.isoformat()
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, uuid.UUID):
        return str(o)
    if isinstance(o, set):
        return list(o)
    if isinstance(o, (bytes, bytearray)):
        return o.decode("utf-8", errors="replace")
    if hasattr(o, "__dict__"):
        return {k: _model_to_dict(v) for k, v in vars(o).items()}
    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")

def _model_to_dict(x: Any) -> Any:
    if x is None or isinstance(x, (str, int, float, bool)):
        return x
    if isinstance(x, (list, tuple, set)):
        return [_model_to_dict(v) for v in x]
    if isinstance(x, dict):
        return {k: _model_to_dict(v) for k, v in x.items()}
    try:
        return _json_default(x)
    except TypeError:
        return str(x)

def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)

def save_state() -> None:
    _write_atomic(
        STATE_INCIDENTS,
        json.dumps({k: _model_to_dict(v) for k, v in INCIDENTS.items()},
                   indent=2, ensure_ascii=False, default=_json_default),
    )
    _write_atomic(
        STATE_RESULTS,
        json.dumps({k: _model_to_dict(v) for k, v in RESULTS.items()},
                   indent=2, ensure_ascii=False, default=_json_default),
    )
    _write_atomic(
        STATE_APPROVALS,
        json.dumps(APPROVALS, indent=2, ensure_ascii=False, default=_json_default),
    )

def load_state() -> None:
    def _load(p: Path, default):
        if not p.exists():
            return default
        return json.loads(p.read_text(encoding="utf-8"))
    try:
        INCIDENTS.update(_load(STATE_INCIDENTS, {}))
    except Exception:
        INCIDENTS.clear()
    try:
        RESULTS.update(_load(STATE_RESULTS, {}))
    except Exception:
        RESULTS.clear()
    try:
        APPROVALS.update(_load(STATE_APPROVALS, {}))
    except Exception:
        APPROVALS.clear()
