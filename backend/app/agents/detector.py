from __future__ import annotations
import uuid
from loguru import logger
from typing import Tuple
from .base import Agent, AgentContext, AgentResult
from ..models.common import AgentName, Severity
from ..models.incident import Incident, IncidentSignal

def _normalize_signal(sig: IncidentSignal) -> IncidentSignal:
    """Ensure consistent units for common labels."""
    label = sig.label.lower()
    unit = (sig.unit or "").lower()

    # latency -> ms
    if "latency" in label or label.endswith("_ms"):
        if unit in ("", None):
            unit = "ms"
        # if someone sent seconds, convert to ms (heuristic)
        if unit in ("s", "sec", "seconds"):
            sig.value = float(sig.value) * 1000.0
            unit = "ms"

    # error_rate -> percent
    if "error_rate" in label or label.endswith("_pct") or label.endswith("_percent"):
        if unit in ("", None):
            unit = "percent"
        # if value is a fraction (0..1), convert to percent
        if float(sig.value) <= 1.0:
            sig.value = float(sig.value) * 100.0
            unit = "percent"

    # 5xx rate: assume rps or rpm; leave as numeric
    return IncidentSignal(
        source=sig.source,
        label=sig.label,
        value=float(sig.value),
        unit=unit or sig.unit,
        window_s=sig.window_s,
        at=sig.at,
    )

def _score_signals(inc: Incident) -> Tuple[int, list[str]]:
    """Return (score, reasons). Higher is worse. Deterministic rules."""
    score = 0
    reasons: list[str] = []

    # Pre-normalize
    signals = [_normalize_signal(s) for s in inc.signals]

    # Heuristics
    # 1) 5xx rate spikes
    for s in signals:
        l = s.label.lower()
        if "5xx" in l or "http_5xx_rate" in l:
            v = float(s.value)
            if v >= 10: score += 3; reasons.append(f"5xx rate very high ({v})")
            elif v >= 5: score += 2; reasons.append(f"5xx rate high ({v})")
            elif v >= 1: score += 1; reasons.append(f"5xx rate elevated ({v})")

    # 2) latency p95
    for s in signals:
        l = s.label.lower()
        if "latency_p95" in l or "p95" in l and "latency" in l:
            v = float(s.value)
            # assume ms
            if v >= 1500: score += 3; reasons.append(f"p95 latency very high ({v} ms)")
            elif v >= 1000: score += 2; reasons.append(f"p95 latency high ({v} ms)")
            elif v >= 800: score += 1; reasons.append(f"p95 latency elevated ({v} ms)")

    # 3) error rate %
    for s in signals:
        l = s.label.lower()
        if "error_rate" in l:
            v = float(s.value)  # percent
            if v >= 10: score += 3; reasons.append(f"error_rate very high ({v}%)")
            elif v >= 5: score += 2; reasons.append(f"error_rate high ({v}%)")
            elif v >= 1: score += 1; reasons.append(f"error_rate elevated ({v}%)")

    return score, reasons

def _map_score_to_severity(score: int) -> Severity:
    if score >= 6: return Severity.critical
    if score >= 4: return Severity.high
    if score >= 2: return Severity.medium
    return Severity.low

class DetectorAgent(Agent):
    name = AgentName.detector

    def run(self, ctx: AgentContext) -> AgentResult:
        inc: Incident = ctx.incident

        # Ensure id
        if not inc.id or not str(inc.id).strip():
            inc.id = f"INC-{uuid.uuid4().hex[:8].upper()}"

        # Compute severity only if not user-specified
        score, reasons = _score_signals(inc)
        computed = _map_score_to_severity(score)
        if inc.severity is None:
            inc.severity = computed
        else:
            # keep the higher of provided vs computed
            order = {Severity.low: 0, Severity.medium: 1, Severity.high: 2, Severity.critical: 3}
            inc.severity = max(inc.severity, computed, key=lambda s: order[s])  # type: ignore[arg-type]

        inc.status = "TRIAGED"
        msg = f"Detector triaged {inc.id} as {inc.severity} (score={score}; " + "; ".join(reasons) + ")"
        logger.info(msg)
        return AgentResult(agent=self.name, ok=True, data=inc, message=msg)
