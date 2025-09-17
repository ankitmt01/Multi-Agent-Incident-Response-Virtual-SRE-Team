
from __future__ import annotations
import argparse, json, time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# stdlib HTTP (same helper shape as simulator)
import http.client
from urllib.parse import urlparse

from simulate_incident import run_one, SCENARIOS  # reuse your simulator

DEFAULT_BASE_URL = "http://localhost:8000"

def _http_request(method: str, url: str, headers: Optional[dict] = None) -> dict:
    p = urlparse(url)
    conn = http.client.HTTPConnection(p.hostname, p.port or 80, timeout=8)
    path = (p.path or "/") + (("?" + p.query) if p.query else "")
    hdrs = {"Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    conn.request(method, path, headers=hdrs)
    resp = conn.getresponse()
    raw = resp.read().decode("utf-8") or "{}"
    try:
        js = json.loads(raw)
    except Exception:
        js = {"_raw": raw}
    return {"status": resp.status, "json": js}

def _get_candidates(base_url: str, incident_id: str, api_key: Optional[str]) -> List[Dict[str, Any]]:
    headers = {"x-api-key": api_key} if api_key else None
    r = _http_request("GET", f"{base_url}/incidents/{incident_id}/candidates", headers=headers)
    if r["status"] != 200:
        raise RuntimeError(f"candidates HTTP {r['status']} → {r['json']}")
    return r["json"]

def evaluate_once(
    base_url: str,
    scenario_key: str,
    csv_path: Path,
    before_min: int,
    after_min: int,
    api_key: Optional[str],
) -> Dict[str, Any]:
    t0 = time.time()
    inc_id = run_one(
        base_url=base_url,
        csv_path=csv_path,
        scenario_key=scenario_key,
        before_min=before_min,
        after_min=after_min,
        mode="overwrite",
        api_key=api_key,
    )
    cands = _get_candidates(base_url, inc_id, api_key)

    policy_ok = sum(1 for c in cands if c.get("policy_ok"))
    policy_block = len(cands) - policy_ok

    val_pass = 0
    val_fail = 0
    val_unknown = 0
    for c in cands:
        v = c.get("validation") or {}
        st = (v.get("status") or "UNKNOWN").upper()
        if st == "PASS":
            val_pass += 1
        elif st == "FAIL":
            val_fail += 1
        else:
            val_unknown += 1

    elapsed = time.time() - t0
    return {
        "incident_id": inc_id,
        "scenario": scenario_key,
        "candidates": len(cands),
        "policy_ok": policy_ok,
        "policy_blocked": policy_block,
        "validation_pass": val_pass,
        "validation_fail": val_fail,
        "validation_unknown": val_unknown,
        "elapsed_sec": round(elapsed, 3),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--scenario", default="all", choices=list(SCENARIOS.keys()) + ["all"])
    ap.add_argument("--runs", type=int, default=1, help="repeat per scenario")
    ap.add_argument("--csv", default="backend/app/data/sample_metrics.csv")
    ap.add_argument("--before-min", type=int, default=10)
    ap.add_argument("--after-min", type=int, default=10)
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--save", default=None, help="path to write JSON results (optional)")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    scenarios = list(SCENARIOS.keys()) if args.scenario == "all" else [args.scenario]

    results: List[Dict[str, Any]] = []
    for sk in scenarios:
        for i in range(args.runs):
            print(f"[eval] {sk} run {i+1}/{args.runs}")
            try:
                r = evaluate_once(base, sk, Path(args.csv), args.before_min, args.after_min, args.api_key)
                results.append(r)
                print(" ", r)
            except Exception as e:
                print(f"  error: {e}")

    # summarize
    total = len(results)
    if total == 0:
        print("[eval] no results to summarize")
        return

    agg = {
        "total_runs": total,
        "avg_candidates": round(sum(r["candidates"] for r in results) / total, 2),
        "policy_ok_rate": round(sum(r["policy_ok"] for r in results) / max(1, sum(r["candidates"] for r in results)), 3),
        "validation_pass_rate": round(sum(r["validation_pass"] for r in results) / max(1, sum(r["candidates"] for r in results)), 3),
        "avg_elapsed_sec": round(sum(r["elapsed_sec"] for r in results) / total, 3),
        "by_scenario": {},
    }
    for sk in scenarios:
        subset = [r for r in results if r["scenario"] == sk]
        if not subset: 
            continue
        ctot = sum(r["candidates"] for r in subset)
        agg["by_scenario"][sk] = {
            "runs": len(subset),
            "avg_candidates": round(ctot / len(subset), 2),
            "policy_ok_rate": round(sum(r["policy_ok"] for r in subset) / max(1, ctot), 3),
            "validation_pass_rate": round(sum(r["validation_pass"] for r in subset) / max(1, ctot), 3),
            "avg_elapsed_sec": round(sum(r["elapsed_sec"] for r in subset) / len(subset), 3),
        }

    print("\n=== SUMMARY ===")
    print(json.dumps(agg, indent=2))

    if args.save:
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        out = {"results": results, "summary": agg, "generated_at": datetime.utcnow().isoformat() + "Z"}
        Path(args.save).write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"[eval] wrote {args.save}")

if __name__ == "__main__":
    main()
