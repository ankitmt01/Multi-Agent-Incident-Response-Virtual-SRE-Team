
from __future__ import annotations
import argparse, json, random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple, Iterable, Optional
import http.client
from urllib.parse import urlparse

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_CSV = "backend/app/data/sample_metrics.csv"

MetricRow = Tuple[datetime, str, float]  # (ts, metric, value)
ERR_NAME = "error_rate_pct"
P95_NAME = "latency_p95_ms"

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _ts_iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def _range_minutes(start: datetime, end: datetime, step_min: int = 1) -> Iterable[datetime]:
    t = start
    delta = timedelta(minutes=step_min)
    while t < end:
        yield t
        t += delta

def _noise(scale: float) -> float:
    return (random.random() * 2 - 1) * scale

def _make_series(
    t0: datetime,
    before_min: int,
    after_min: int,
    base_err_pct: float,
    base_p95_ms: float,
    drop_err_rel: float = 0.0,
    drop_p95_rel: float = 0.0,
    cadence_min: int = 1,
) -> List[MetricRow]:
    rows: List[MetricRow] = []
    t_start = t0 - timedelta(minutes=before_min)
    t_end   = t0 + timedelta(minutes=after_min)
    for ts in _range_minutes(t_start, t0, cadence_min):
        rows.append((ts, ERR_NAME, base_err_pct + _noise(base_err_pct * 0.05)))
        rows.append((ts, P95_NAME, base_p95_ms + _noise(base_p95_ms * 0.05)))
    err_after = base_err_pct * (1.0 - drop_err_rel)
    p95_after = base_p95_ms * (1.0 - drop_p95_rel)
    for ts in _range_minutes(t0, t_end, cadence_min):
        rows.append((ts, ERR_NAME, max(0.0, err_after + _noise(base_err_pct * 0.05))))
        rows.append((ts, P95_NAME, max(0.0, p95_after + _noise(base_p95_ms * 0.05))))
    return rows

# -------------------------- Scenarios (edit freely) --------------------------

SCENARIOS = {
    "rollback_pass": {
        "service": "checkout",
        "suspected_cause": "recent deploy",
        "signals": [
            {"name":"5xx_rate","value":1.6,"unit":"%","window_s":60},
            {"name":"latency_p95_ms","value":1200,"unit":"ms","window_s":60},
        ],
        "metrics": {"base_err_pct": 1.6, "base_p95_ms": 1200, "drop_err_rel": 0.35, "drop_p95_rel": 0.25},
    },
    "cache_pass": {
        "service": "checkout",
        "suspected_cause": "cache cold start",
        "signals": [
            {"name":"5xx_rate","value":0.4,"unit":"%","window_s":60},
            {"name":"latency_p95_ms","value":1000,"unit":"ms","window_s":60},
        ],
        "metrics": {"base_err_pct": 0.4, "base_p95_ms": 1000, "drop_err_rel": 0.05, "drop_p95_rel": 0.15},
    },
    "no_change_fail": {
        "service": "checkout",
        "suspected_cause": "unknown",
        "signals": [
            {"name":"5xx_rate","value":0.8,"unit":"%","window_s":60},
            {"name":"latency_p95_ms","value":900,"unit":"ms","window_s":60},
        ],
        "metrics": {"base_err_pct": 0.8, "base_p95_ms": 900, "drop_err_rel": 0.01, "drop_p95_rel": 0.01},
    },
}

# ------------------------------- HTTP helpers --------------------------------

def _http_request(method: str, url: str, body: Optional[dict] = None, headers: Optional[dict] = None) -> dict:
    """Small stdlib client with verbose error visibility."""
    p = urlparse(url)
    conn = http.client.HTTPConnection(p.hostname, p.port or 80, timeout=5)
    path = (p.path or "/") + (("?" + p.query) if p.query else "")
    payload = json.dumps(body) if body is not None else None
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    conn.request(method, path, body=payload, headers=hdrs)
    resp = conn.getresponse()
    raw = resp.read().decode("utf-8") or "{}"
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = {"_raw": raw}
    return {"status": resp.status, "json": parsed}

def _detect(base_url: str, service: str, suspected_cause: str, signals: List[dict], api_key: Optional[str]) -> Optional[str]:
    headers = {"x-api-key": api_key} if api_key else None
    r = _http_request("POST", f"{base_url}/incidents/detect",
                      {"service": service, "suspected_cause": suspected_cause, "signals": signals},
                      headers=headers)
    if r["status"] >= 300:
        print(f"[detect] HTTP {r['status']} → {r['json']}")
        return None
    return (r.get("json") or {}).get("id")

def _approve(base_url: str, incident_id: str, api_key: Optional[str]) -> None:
    headers = {"x-api-key": api_key} if api_key else None
    r = _http_request("POST", f"{base_url}/incidents/{incident_id}/approve?approved=true", headers=headers)
    if r["status"] >= 300:
        print(f"[approve] HTTP {r['status']} → {r['json']}")

def _run_pipeline(base_url: str, incident_id: str, api_key: Optional[str]) -> None:
    headers = {"x-api-key": api_key} if api_key else None
    r = _http_request("POST", f"{base_url}/incidents/{incident_id}/run", headers=headers)
    if r["status"] >= 300:
        print(f"[run] HTTP {r['status']} → {r['json']}")

# ---------------------------------- Driver -----------------------------------

def run_one(
    base_url: str,
    csv_path: Path,
    scenario_key: str,
    before_min: int,
    after_min: int,
    mode: str,
    api_key: Optional[str],
) -> str:
    sc = SCENARIOS[scenario_key]
    t0 = _now_utc()

    inc_id = _detect(base_url, sc["service"], sc["suspected_cause"], sc["signals"], api_key=api_key)
    if not inc_id:
        raise SystemExit(f"Failed to create incident for scenario '{scenario_key}'")

    m = sc["metrics"]
    rows = _make_series(
        t0=t0,
        before_min=before_min,
        after_min=after_min,
        base_err_pct=m["base_err_pct"],
        base_p95_ms=m["base_p95_ms"],
        drop_err_rel=m["drop_err_rel"],
        drop_p95_rel=m["drop_p95_rel"],
    )

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    exists = csv_path.exists()
    mode_flag = "a" if (exists and mode == "append") else "w"
    with csv_path.open(mode_flag, encoding="utf-8", newline="") as f:
        if mode_flag == "w":
            f.write("ts,metric,value\n")
        for ts, metric, value in rows:
            f.write(f"{_ts_iso_z(ts)},{metric},{value:.4f}\n")

    _approve(base_url, inc_id, api_key=api_key)
    _run_pipeline(base_url, inc_id, api_key=api_key)

    return inc_id

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--csv", default=DEFAULT_CSV)
    ap.add_argument("--scenario", default="rollback_pass", choices=list(SCENARIOS.keys()) + ["all"])
    ap.add_argument("--before-min", type=int, default=10)
    ap.add_argument("--after-min", type=int, default=10)
    ap.add_argument("--mode", choices=["overwrite","append"], default="overwrite")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--api-key", default=None)
    args = ap.parse_args()

    base_url = args.base_url.rstrip("/")
    csv_path = Path(args.csv)

    scenarios: List[str] = []
    if args.scenario == "all":
        scenarios = list(SCENARIOS.keys()) * args.count
    else:
        scenarios = [args.scenario] * args.count

    print(f"[simulate] base_url={base_url} csv={csv_path} mode={args.mode}")
    for i, sk in enumerate(scenarios, 1):
        inc_id = run_one(
            base_url=base_url,
            csv_path=csv_path,
            scenario_key=sk,
            before_min=args.before_min,
            after_min=args.after_min,
            mode=("append" if i > 1 or args.mode == "append" else args.mode),
            api_key=args.api_key,
        )
        print(f"[simulate] {i}/{len(scenarios)} scenario={sk} → incident_id={inc_id}")

if __name__ == "__main__":
    main()
