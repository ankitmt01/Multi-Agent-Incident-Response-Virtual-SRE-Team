# backend/app/validator/validator.py
from __future__ import annotations
import os, csv
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

CSV_PATH = Path(os.getenv("VALIDATOR_CSV", "backend/app/data/sample_metrics.csv"))
BEFORE_MIN = int(os.getenv("VALIDATOR_BEFORE_MIN", "10"))
AFTER_MIN  = int(os.getenv("VALIDATOR_AFTER_MIN", "10"))

# KPIs we look at in the sample CSV
KPI_KEYS = ["5xx_rate", "latency_p95_ms"]

def _to_dt(obj: Any) -> datetime:
    """Parse ISO-ish strings or pass through datetimes."""
    if isinstance(obj, datetime):
        return obj
    if isinstance(obj, str):
        s = obj.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(s)
        except Exception:
            pass
    # fallback: now (naive)
    return datetime.utcnow().replace(tzinfo=None)

def _naive_utc(dt: datetime) -> datetime:
    """Convert any aware dt to naive UTC; leave naive as-is."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)

def _parse_ts(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return _naive_utc(_to_dt(s))
    except Exception:
        return None

def _read_rows(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            ts = r.get("ts") or r.get("timestamp") or r.get("time") or r.get("datetime")
            r["_ts"] = _parse_ts(ts)
            # Coerce numeric-looking fields to floats
            for k, v in list(r.items()):
                if k == "_ts" or v is None:
                    continue
                try:
                    if isinstance(v, str) and v.strip() == "":
                        r[k] = None
                    else:
                        r[k] = float(v)
                except Exception:
                    pass
            rows.append(r)
    return rows

def _window_mean(rows: List[Dict[str, Any]], start: datetime, end: datetime) -> Dict[str, Optional[float]]:
    start = _naive_utc(start)
    end   = _naive_utc(end)
    sums   = {k: 0.0 for k in KPI_KEYS}
    counts = {k: 0     for k in KPI_KEYS}
    for r in rows:
        ts = r.get("_ts")
        if not isinstance(ts, datetime):
            continue
        ts = _naive_utc(ts)
        if ts < start or ts >= end:
            continue
        for k in KPI_KEYS:
            val = r.get(k)
            if isinstance(val, (int, float)):
                sums[k] += float(val)
                counts[k] += 1
    means: Dict[str, Optional[float]] = {}
    for k in KPI_KEYS:
        means[k] = (sums[k] / counts[k]) if counts[k] > 0 else None
    return means

def validate(incident: Any, candidate: Dict[str, Any], window: int = 60) -> Dict[str, Any]:
    """
    Offline heuristic validation using sample_metrics.csv around incident.created_at.
    Returns: {status, before, after, kpi_deltas, notes}
    """
    rows = _read_rows(CSV_PATH)

    # Anchor time: incident.created_at if present, else now
    t0_attr = getattr(incident, "created_at", None)
    t0 = _naive_utc(_to_dt(t0_attr)) if t0_attr else _naive_utc(datetime.utcnow())

    before = _window_mean(rows, t0 - timedelta(minutes=BEFORE_MIN), t0)
    after  = _window_mean(rows, t0, t0 + timedelta(minutes=AFTER_MIN))

    deltas: Dict[str, Optional[float]] = {}
    checks: List[bool] = []
    for k in KPI_KEYS:
        b = before.get(k)
        a = after.get(k)
        if b is None or a is None:
            continue
        deltas[k] = a - b
        # Lower is better for both sample KPIs
        checks.append(a <= b)

    status = "UNKNOWN"
    if checks:
        status = "PASS" if all(checks) else "FAIL"

    return {
        "status": status,
        "before": before,
        "after": after,
        "kpi_deltas": deltas,
        "notes": "Offline heuristic; lower is better for 5xx_rate and latency_p95_ms.",
    }
