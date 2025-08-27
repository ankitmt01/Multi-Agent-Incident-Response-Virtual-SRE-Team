from __future__ import annotations
from loguru import logger
from typing import List, Dict, Any
from .base import Agent, AgentContext, AgentResult
from ..models.common import AgentName
from ..models.incident import Incident, RemediationCandidate, IncidentSignal

def _has_label(signals: List[IncidentSignal], needle: str) -> bool:
    return any(needle in s.label.lower() for s in signals)

def _get_value(signals: List[IncidentSignal], label_contains: str, default: float = 0.0) -> float:
    for s in signals:
        if label_contains in s.label.lower():
            try:
                return float(s.value)
            except Exception:
                return default
    return default

class RemediatorAgent(Agent):
    name = AgentName.remediator

    def run(self, ctx: AgentContext) -> AgentResult:
        inc: Incident = ctx.incident
        sigs = inc.signals
        cause = (inc.suspected_cause or "").lower()

        candidates: List[RemediationCandidate] = []

        # Heuristic 1: bad deploy / 5xx surge
        if "deploy" in cause or _has_label(sigs, "5xx"):
            candidates.append(RemediationCandidate(
                name="Rollback last deploy",
                steps=[
                    "Freeze traffic if supported",
                    "Git revert last prod tag and redeploy previous known-good version",
                    "Run smoke tests and monitor 5xx & p95",
                ],
                actions=[
                    {"action_type": "deploy.rollback", "resource": "service", "target": inc.service, "requires_approval": True},
                    {"action_type": "test.run_smoke", "resource": "pipeline", "target": inc.service, "requires_approval": False},
                    {"action_type": "traffic.monitor", "resource": "metrics", "target": ["5xx", "latency_p95"], "requires_approval": False}
                ],
                risks=["Config drift between versions", "Partial rollback artifacts"],
                rollback=["Re-apply current version if metrics regress"],
                rationale="5xx surge coupled with suspected bad deploy → rollback is the fastest blast-radius reducer.",
                predicted_impact={"error_rate": "-80%", "latency_p95": "-30%"},
            ))
            candidates.append(RemediationCandidate(
                name="Toggle off recent feature flag",
                steps=[
                    "Disable the most recent flag rollout for the affected service",
                    "Warm cache and monitor error rate",
                ],
                actions=[
                    {"action_type": "feature.toggle", "resource": "flag", "target": "latest_flag_for_service", "requires_approval": True},
                    {"action_type": "cache.warm", "resource": "cache", "target": inc.service, "requires_approval": False},
                ],
                risks=["Hidden dependencies on the feature path"],
                rollback=["Re-enable flag after fix validated"],
                rationale="If the surge aligns with a feature rollout, toggling off is low-risk + fast.",
                predicted_impact={"error_rate": "-40%", "latency_p95": "-10%"},
            ))

        # Heuristic 2: latency spike likely DB pool / downstream saturation
        if "db" in cause or _has_label(sigs, "latency_p95"):
            p95 = _get_value(sigs, "latency_p95", 0.0)
            candidates.append(RemediationCandidate(
                name="Increase DB connection pool & enable circuit breaker",
                steps=[
                    "Increase DB pool size by 20%",
                    "Enable circuit breaker for downstream calls",
                    "Add rate limit to hotspot endpoints",
                    "Run smoke tests",
                ],
                actions=[
                    {"action_type": "db.config_change", "resource": "db_pool", "target": inc.service, "delta_percent": 20, "requires_approval": True},
                    {"action_type": "traffic.policy", "resource": "circuit_breaker", "target": inc.service, "requires_approval": True},
                    {"action_type": "traffic.policy", "resource": "rate_limit", "target": "hot_endpoints", "requires_approval": True},
                    {"action_type": "test.run_smoke", "resource": "pipeline", "target": inc.service, "requires_approval": False},
                ],
                risks=["DB saturation if mis-sized", "Potential cascading throttling"],
                rollback=["Restore previous pool size", "Disable breaker & rate-limit"],
                rationale=f"Tail latency ({int(p95)}ms) with 5xx suggests saturation; pool + breaker typically reduces both.",
                predicted_impact={"error_rate": "-60%", "latency_p95": "-25%"},
            ))

        # Heuristic 3: cache stampede / external API path
        if "cache" in cause or "stampede" in cause:
            candidates.append(RemediationCandidate(
                name="Mitigate cache stampede",
                steps=[
                    "Enable request coalescing",
                    "Increase TTL for hot keys",
                    "Enable stale-while-revalidate",
                ],
                actions=[
                    {"action_type": "cache.config", "resource": "coalescing", "target": inc.service, "requires_approval": True},
                    {"action_type": "cache.config", "resource": "ttl", "target": "hot_keys", "delta_percent": 50, "requires_approval": True},
                    {"action_type": "cache.config", "resource": "swr", "target": inc.service, "requires_approval": True},
                ],
                risks=["Cache growth and staleness"],
                rollback=["Revert TTL & SWR sett]()
