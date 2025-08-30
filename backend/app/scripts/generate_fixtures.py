from __future__ import annotations
from pathlib import Path
from datetime import datetime, timedelta
import csv
import sys

def write_metrics_csv(service: str, minutes: int = 120):
    data_dir = Path(__file__).resolve().parents[2] / "data" / "metrics"
    data_dir.mkdir(parents=True, exist_ok=True)
    f = data_dir / f"{service}.csv"
    now = datetime.utcnow()
    rows = []
    for i in range(minutes):
        ts = now - timedelta(minutes=(minutes - 1 - i))
        # baseline 2% error → trending to 8% near the end; p95 from 600→1500ms
        err = 2.0 + (6.0 * i / max(1, minutes - 1))
        p95 = 600.0 + (900.0 * i / max(1, minutes - 1))
        rows.append((ts.isoformat(), round(err, 3), round(p95, 1)))
    with f.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["ts", "error_rate_pct", "latency_p95_ms"])
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {f}")

if __name__ == "__main__":
    svc = sys.argv[1] if len(sys.argv) > 1 else "payments"
    write_metrics_csv(svc)
