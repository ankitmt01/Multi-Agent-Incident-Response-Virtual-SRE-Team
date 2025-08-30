from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Tuple
from pathlib import Path
from datetime import datetime, timedelta
import csv
from loguru import logger
from .base import Agent, AgentContext, AgentResult
from ..models.common import AgentName
from ..models.incident import ValidationResult, RemediationCandidate

@dataclass
class KPIs:
    error_rate_pct: float
    latency_p95_ms: float

def _parse_percent_string(s: str) -> float:
    """
    '-60%' -> -0.60 ; '20%' -> 0.20 ; '0.2' -> 0.2 ; '0' -> 0.0
    """
    s = str(s).strip()
    if s.endswith("%"):
        return float(s[:-1]) / 100.0
    try:
        return float(s)
    except Exception:
        return 0.0

def _apply_predicted_impact(before: KPIs, predicted: Dict[str, float | str]) -> KPIs:
    err = before.error_rate_pct
    p95 = before.latency_p95_ms
    if "error_rate" in predicted:
        delta = _parse_percent_string(predicted["error_rate"])
        err = max(0.0, err * (1.0 + delta))  # delta is typically negative e.g. -0.6
    if "latency_p95" in predicted:
        delta = _parse_percent_string(predicted["latency_p95"])
        p95 = max(0.0, p95 * (1.0 + delta))
    return KPIs(error_rate_pct=err, latency_p95_ms=p95)

def _fallback_impact(c: RemediationCandidate, before: KPIs) -> KPIs:
    """
    If a candidate has no predicted_impact, apply conservative defaults based on its name.
    """
    name = (c.name or "").lower()
    if "rollback" in name:
        return _apply_predicted_impact(before, {"error_rate": "-0.50", "latency_p95": "-0.20"})
    if "db" in name or "pool" in name:
        return _apply_predicted_impact(before, {"error_rate": "-0.30", "latency_p95": "-0.25"})
    if "cache" in name:
        return _apply_predicted_impact(before, {"error_rate": "-0.25", "latency_p95": "-0.15"})
    if "external" in name or "api" in name:
        return _apply_predicted_impact(before, {"error_rate": "-0.40", "latency_p95": "-0.20"})
    # generic
    return _apply_predicted_impact(before, {"error_rate": "-0.10", "latency_p95": "-0.10"})

def _load_metrics(service: str) -> List[Tuple[datetime, float, float]]:
    """
    Return list of (ts, error_rate_pct, latency_p95_ms) from CSV.
    If no CSV exists, generate a small synthetic series in-memory.
    """
    metrics_dir = Path(__file__).resolve().parents[2] / "data" / "metrics"
    f = metrics_dir / f"{service}.csv"
    rows: List[Tuple[datetime, float, float]] = []
    if f.exists():
        with f.open("r", encoding="utf-8") as fh:
            r = csv.DictReader(fh)
            for row in r:
                try:
                    ts = datetime.fromisoformat(row["ts"])
                    err = float(row["error_rate_pct"])
                    p95 = float(row["latency_p95_ms"])
                    rows.append((ts, err, p95))
                except Exception:
                    continue
    else:
        # fallback synthetic: 60 minutes, trending worse in last 15
        now = datetime.utcnow()
        for i in range(60):
            ts = now - timedelta(minutes=59 - i)
            base_err = 2.0 + (0.05 * i)          # 2% to ~5%
            base_p95 = 600 + (8 * i)             # 600ms to ~1080ms
            rows.append((ts, base_err, base_p95))
    return rows

def _window_avg(rows: List[Tuple[datetime, float, float]], minutes: int) -> KPIs:
    if not rows:
        return KPIs(error_rate_pct=0.0, latency_p95_ms=0.0)
    cutoff = rows[-1][0] - timedelta(minutes=minutes)
    use = [r for r in rows if r[0] >= cutoff]
    if not use:
        use = rows[-minutes:] if len(rows) >= minutes else rows
    err = sum(r[1] for r in use) / len(use)
    p95 = sum(r[2] for r in use) / len(use)
    return KPIs(error_rate_pct=err, latency_p95_ms=p95)

class ValidatorAgent(Agent):
    name = AgentName.validator

    def run(self, ctx: AgentContext) -> AgentResult:
        s = ctx.settings
        inc = ctx.incident

        # Load metrics for this service
        series = _load_metrics(inc.service)
        before = _window_avg(series, s.validation_window_minutes)

        results: List[ValidationResult] = []
        for c in inc.remediation_candidates:
            # Skip blocked candidates (policy)
            if getattr(c, "policy_status", "") == "blocked":
                results.append(ValidationResult(
                    candidate=c.name, passed=False, notes="Blocked by Policy Guard",
                    kpi_before={"error_rate": before.error_rate_pct, "latency_p95": before.latency_p95_ms},
                    kpi_after={"error_rate": before.error_rate_pct, "latency_p95": before.latency_p95_ms},
                ))
                continue

            predicted = c.predicted_impact or {}
            after = _apply_predicted_impact(before, predicted) if predicted else _fallback_impact(c, before)

            # Decide pass/fail
            err_impr = (before.error_rate_pct - after.error_rate_pct) / max(before.error_rate_pct, 1e-6)
            p95_impr = (before.latency_p95_ms - after.latency_p95_ms) / max(before.latency_p95_ms, 1e-6)

            pass_rules = []
            if err_impr >= s.validation_err_improvement_pct:
                pass_rules.append(f"error_rate improved {err_impr:.0%} ≥ {s.validation_err_improvement_pct:.0%}")
            if p95_impr >= s.validation_p95_improvement_pct:
                pass_rules.append(f"p95 improved {p95_impr:.0%} ≥ {s.validation_p95_improvement_pct:.0%}")
            if after.error_rate_pct <= s.validation_err_abs_target_pct:
                pass_rules.append(f"error_rate ≤ {s.validation_err_abs_target_pct}%")
            if after.latency_p95_ms <= s.validation_p95_abs_target_ms:
                pass_rules.append(f"p95 ≤ {int(s.validation_p95_abs_target_ms)}ms")

            passed = len(pass_rules) >= 2  # require two signals to pass (tweakable)

            note_bits = []
            if predicted:
                note_bits.append("used predicted_impact")
            else:
                note_bits.append("used heuristic impact")
            if getattr(c, "policy_status", "") == "needs_approval":
                note_bits.append("requires approval")

            results.append(ValidationResult(
                candidate=c.name,
                passed=passed,
                notes="; ".join(pass_rules) if passed else "did not meet thresholds; " + ", ".join(pass_rules) if pass_rules else "no thresholds met",
                kpi_before={"error_rate": round(before.error_rate_pct, 3), "latency_p95": round(before.latency_p95_ms, 1)},
                kpi_after={"error_rate": round(after.error_rate_pct, 3), "latency_p95": round(after.latency_p95_ms, 1)},
            ))

        inc.validation_results = results
        return AgentResult(agent=self.name, ok=True, data=inc, message=f"Validated {len(results)} candidates")
