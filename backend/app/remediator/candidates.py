
# # backend/app/remediator/candidates.py
# from __future__ import annotations
# from typing import Any, Dict, List, Optional
# import itertools
# from ..policy.policy_guard import evaluate_plan

# def _plan_id(prefix: str, n: int) -> str:
#     return f"{prefix}-{n}"

# def _mk_step(action_type: str, description: str, **kw) -> Dict[str, Any]:
#     return {"action_type": action_type, "description": description, **kw}

# def generate_candidates(incident: Any, evidence: List[Any]) -> List[Dict[str, Any]]:
#     """
#     Deterministic candidates based on suspected_cause and common patterns.
#     Returns list of dicts with fields: id, title, env, steps[], rationale, predicted_impact{}, policy_violations[].
#     """
#     svc = getattr(incident, "service", None) or "service"
#     cause = (getattr(incident, "suspected_cause", None) or "").lower()
#     env = "prod"  # default; adjust as needed

#     candidates: List[Dict[str, Any]] = []

#     if "deploy" in cause:
#         # Candidate A: rollback last deployment
#         steps = [
#             _mk_step("backup", "Snapshot current config/artifacts before rollback.", service=svc),
#             _mk_step("config_change", "Rollback to the last known good release (blue/green).", service=svc, command="deploy rollback --to=previous"),
#             _mk_step("read", "Verify health and KPIs post-rollback for 10 minutes.", service=svc),
#         ]
#         candidates.append({
#             "id": _plan_id("rollback", 1),
#             "title": "Safe rollback to last known good",
#             "env": env,
#             "steps": steps,
#             "rationale": "Recent deploy correlated with spike; rollback is the fastest mitigation.",
#             "predicted_impact": {"error_rate": -0.5, "latency_p95_ms": -0.3},
#         })

#         # Candidate B: feature-flag safe mode (without disabling globally)
#         steps = [
#             _mk_step("config_change", "Enable service-level 'safe_mode' flag for checkout only.", service=svc, command="ff enable safe_mode --service=checkout"),
#             _mk_step("read", "Observe 5xx and p95 for 10 minutes.", service=svc),
#         ]
#         candidates.append({
#             "id": _plan_id("flag", 1),
#             "title": "Enable service-level safe mode",
#             "env": env,
#             "steps": steps,
#             "rationale": "Reduces risky paths without global impact.",
#             "predicted_impact": {"error_rate": -0.35, "latency_p95_ms": -0.2},
#         })

#     elif "db" in cause:
#         # Candidate A: increase DB pool / connection tuning
#         steps = [
#             _mk_step("config_change", "Increase DB pool size by 20% for the service.", service=svc, command="cfg set db.pool_size +20%"),
#             _mk_step("restart", "Gracefully restart service to apply config (one instance at a time).", service=svc),
#             _mk_step("read", "Observe saturation and p95 for 10 minutes.", service=svc),
#         ]
#         candidates.append({
#             "id": _plan_id("dbpool", 1),
#             "title": "Tune DB pool conservatively",
#             "env": env,
#             "steps": steps,
#             "rationale": "Alleviates connection queueing under burst.",
#             "predicted_impact": {"error_rate": -0.25, "latency_p95_ms": -0.25},
#         })

#         # Candidate B: add query cache / warm cache
#         steps = [
#             _mk_step("script", "Warm cache for top N queries.", service=svc, command="scripts/warm_cache.py --top=100"),
#             _mk_step("read", "Observe cache hit rate & p95 for 10 minutes.", service=svc),
#         ]
#         candidates.append({
#             "id": _plan_id("cache", 1),
#             "title": "Warm cache for high-QPS queries",
#             "env": env,
#             "steps": steps,
#             "rationale": "Cuts read load while DB stabilizes.",
#             "predicted_impact": {"error_rate": -0.15, "latency_p95_ms": -0.2},
#         })

#     else:
#         # Generic spike playbook
#         steps = [
#             _mk_step("config_change", "Throttle the most expensive endpoint by 10% for 15 minutes.", service=svc, command="rate-limit set /expensive 0.9"),
#             _mk_step("script", "Warm CDN/cache for hot paths.", service=svc, command="scripts/warm_paths.py --paths=/hot1,/hot2"),
#             _mk_step("read", "Observe KPIs for 10 minutes.", service=svc),
#         ]
#         candidates.append({
#             "id": _plan_id("throttle", 1),
#             "title": "Gentle throttle + warm caches",
#             "env": env,
#             "steps": steps,
#             "rationale": "Reduce pressure quickly while preserving most traffic.",
#             "predicted_impact": {"error_rate": -0.2, "latency_p95_ms": -0.15},
#         })

#         steps = [
#             _mk_step("scale", "Scale out service by +1 replica (HPA min surge).", service=svc, command="hpa set --min+1"),
#             _mk_step("read", "Observe KPIs for 10 minutes.", service=svc),
#         ]
#         candidates.append({
#             "id": _plan_id("scale", 1),
#             "title": "Conservative scale-out",
#             "env": env,
#             "steps": steps,
#             "rationale": "Adds headroom without risky changes.",
#             "predicted_impact": {"error_rate": -0.1, "latency_p95_ms": -0.1},
#         })

#     # Attach policy violations
#     out: List[Dict[str, Any]] = []
#     for c in candidates:
#         v = evaluate_plan(getattr(incident, "id", "unknown"), c, None)
#         c = {**c, "policy_violations": v, "policy_ok": len(v) == 0}
#         out.append(c)
#     return out




# backend/app/remediator/candidates.py
from __future__ import annotations
from typing import Any, Dict, List
from ..policy.policy_guard import evaluate_plan

def _base_env(incident) -> str:
    # naive guess from service; refine as needed or pass via incident metadata
    _ = (getattr(incident, "service", "") or "").lower()
    return "staging"  # safe default for demos

def _candidate_id(prefix: str, incident) -> str:
    sid = getattr(incident, "id", "inc")
    return f"{prefix}-{sid[:8]}"

def _deploy_rollback(incident, env: str, service: str) -> Dict[str, Any]:
    return {
        "id": _candidate_id("rollback", incident),
        "title": f"Rollback recent deploy for {service}",
        "env": env,
        "service": service,
        "rationale": "Recent deploy suspected; rollback to last known good.",
        "predicted_impact": {"error_rate_pct": -0.5, "latency_p95_ms": -200},
        "steps": [
            {"action_type": "read", "env": env, "service": service, "cmd": "fetch deploy status"},
            {"action_type": "deploy", "env": env, "service": service, "targets": [service], "version": "previous"},
            {"action_type": "restart", "env": env, "service": service, "targets": [service]},
            {"action_type": "read", "env": env, "service": service, "cmd": "verify health"},
        ],
    }

def _db_pool_tune(incident, env: str, service: str) -> Dict[str, Any]:
    return {
        "id": _candidate_id("db-pool", incident),
        "title": f"Tune DB pool for {service}",
        "env": env,
        "service": service,
        "rationale": "High p95 + low 5xx suggests saturation; raise pool, add backoff.",
        "predicted_impact": {"error_rate_pct": -0.2, "latency_p95_ms": -150},
        "steps": [
            {"action_type": "read", "env": env, "service": service, "cmd": "check DB pool graphs"},
            {"action_type": "config_change", "env": env, "service": service, "targets": [service], "key": "db.pool.max", "value": "+20%"},
            {"action_type": "restart", "env": env, "service": service, "targets": [service]},
        ],
    }

def _cache_warm(incident, env: str, service: str) -> Dict[str, Any]:
    return {
        "id": _candidate_id("cache-warm", incident),
        "title": f"Warm cache for {service}",
        "env": env,
        "service": service,
        "rationale": "Cache miss storm after deploy; warm critical keys.",
        "predicted_impact": {"error_rate_pct": -0.1, "latency_p95_ms": -100},
        "steps": [
            {"action_type": "read", "env": env, "service": service, "cmd": "inspect cache hit-rate"},
            {"action_type": "config_change", "env": env, "service": service, "targets": [service], "key": "cache.prefill", "value": "on"},
        ],
    }

def generate_candidates(incident, evidence_objs: List[Any]) -> List[Dict[str, Any]]:
    service = (getattr(incident, "service", "") or "generic").lower()
    env = _base_env(incident)

    plans: List[Dict[str, Any]] = [
        _deploy_rollback(incident, env, service),
        _db_pool_tune(incident, env, service),
        _cache_warm(incident, env, service),
    ]

    # Evaluate policies; assume approval can be read externally if needed
    approved = False  # runtime approval is checked at execution time; keep candidates conservative
    for p in plans:
        evalr = evaluate_plan(p, approved=approved)
        p["policy_ok"] = bool(evalr["policy_ok"])
        p["policy_violations"] = evalr["policy_violations"]
        p["violations_by_step"] = evalr["violations_by_step"]

    return plans
