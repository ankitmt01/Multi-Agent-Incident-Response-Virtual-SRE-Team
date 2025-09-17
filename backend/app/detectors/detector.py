# from typing import List
# from ..models import Signal

# def normalize(signals: List[Signal]):
#     return signals

# def infer_severity(signals: List[Signal]) -> str:
#     names = {s.name: s for s in signals}
#     five_xx = names.get("5xx_rate")
#     p95 = names.get("latency_p95_ms") or names.get("latency_p95_s")
#     cond1 = five_xx and five_xx.value >= 1.0  # percent
#     if p95 is None:
#         cond2 = False
#     elif p95.unit.lower().endswith("ms"):
#         cond2 = p95.value >= 1000
#     else:
#         cond2 = p95.value >= 1.0
#     if cond1 and cond2:
#         return "HIGH"
#     if cond1 or cond2:
#         return "MEDIUM"
#     return "LOW"




# backend/app/detectors/detector.py
from __future__ import annotations
import os
from typing import Any, Dict, List

# ---------- Tunables (env; sensible defaults) ----------
ERR_HIGH_PCT = float(os.getenv("DETECT_ERR_HIGH", "1.0"))      # %
ERR_MED_PCT  = float(os.getenv("DETECT_ERR_MED",  "0.5"))      # %
P95_HIGH_MS  = float(os.getenv("DETECT_P95_HIGH", "1000"))     # ms
P95_MED_MS   = float(os.getenv("DETECT_P95_MED",  "800"))      # ms

# Optionally use the time window to dampen noise (seconds)
MIN_WINDOW_S = int(os.getenv("DETECT_MIN_WINDOW_S", "30"))

def _coerce_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default

def _norm_unit(name: str, value: float, unit: str | None) -> float:
    """Normalize common metrics to base units:
       - 5xx_rate/error_rate: percent -> percent (keep % scale here)
       - latency_p95: ms
    """
    n = (name or "").lower()
    u = (unit or "").lower().strip()

    # Error rate in %
    if n in {"5xx", "5xx_rate", "error_rate", "http_5xx_rate"}:
        if u in {"", "%", "percent", "pct"}:
            return value
        # If an absolute fraction slipped in, convert to %
        if u in {"ratio", "fraction"} or (0 <= value <= 1 and u == ""):
            return value * 100.0
        return value

    # Latency to ms
    if n in {"latency_p95", "latency_p95_ms", "p95_latency", "latency"}:
        if u in {"ms", "millisecond", "milliseconds", ""}:
            return value
        if u in {"s", "sec", "secs", "second", "seconds"}:
            return value * 1000.0
        if u in {"us", "µs"}:
            return value / 1000.0
        return value

    # Default: return as-is
    return value

def normalize(signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize incoming signals to consistent units & keys."""
    out: List[Dict[str, Any]] = []
    for s in signals or []:
        name = (s.get("name") or "").strip()
        unit = s.get("unit")
        value = _coerce_float(s.get("value"))
        win   = int(_coerce_float(s.get("window_s"), 0))
        if win and win < MIN_WINDOW_S:
            # very short windows are noisy; keep but mark
            pass
        norm_val = _norm_unit(name, value, unit)
        out.append({
            "name": name,
            "value": norm_val,
            "unit": unit,
            "window_s": win or None
        })
    return out

def _get(signals: List[Dict[str, Any]], *names: str, default: float = 0.0) -> float:
    names_lc = {n.lower() for n in names}
    for s in signals:
        n = (s.get("name") or "").lower()
        if n in names_lc:
            return _coerce_float(s.get("value"), default)
    return default

def infer_severity(signals: List[Dict[str, Any]]) -> str:
    """Rule-based severity:
       HIGH   if (error% >= ERR_HIGH_PCT and p95 >= P95_HIGH_MS) or
                error% >= ERR_HIGH_PCT * 2  or p95 >= P95_HIGH_MS * 1.5
       MEDIUM if error% >= ERR_MED_PCT or p95 >= P95_MED_MS
       else LOW
    """
    sigs = normalize(signals)

    err_pct = _get(sigs, "5xx_rate", "5xx", "error_rate", "http_5xx_rate", default=0.0)
    p95_ms  = _get(sigs, "latency_p95", "latency_p95_ms", "p95_latency", "latency", default=0.0)

    # High rules (joint or extreme single-signal)
    if (err_pct >= ERR_HIGH_PCT and p95_ms >= P95_HIGH_MS) \
       or (err_pct >= ERR_HIGH_PCT * 2) \
       or (p95_ms >= P95_HIGH_MS * 1.5):
        return "HIGH"

    # Medium rules
    if (err_pct >= ERR_MED_PCT) or (p95_ms >= P95_MED_MS):
        return "MEDIUM"

    return "LOW"
