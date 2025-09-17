# # backend/app/policy/policy_guard.py
# from __future__ import annotations
# from typing import Any, Dict, List, Optional
# from datetime import datetime, time
# import os

# # Optional: consult shared approvals/state if available
# try:
#     from .. import store  # has APPROVALS: Dict[str, bool]
# except Exception:
#     class _Store:
#         APPROVALS = {}
#     store = _Store()

# PEAK_START = time.fromisoformat(os.getenv("PEAK_START", "09:00:00"))
# PEAK_END   = time.fromisoformat(os.getenv("PEAK_END",   "21:00:00"))
# PROD_ENVS  = set((os.getenv("PROD_ENVS", "prod,production")).split(","))

# def _is_peak(now: Optional[datetime] = None) -> bool:
#     now = now or datetime.now()
#     t = now.time()
#     return PEAK_START <= t <= PEAK_END

# def _has_backup_step(steps: List[Dict[str, Any]]) -> bool:
#     for s in steps:
#         d = (s.get("description") or "") + " " + (s.get("command") or "")
#         if "backup" in d.lower() or s.get("action_type") == "backup":
#             return True
#     return False

# def evaluate_plan(
#     incident_id: str,
#     plan: Dict[str, Any],
#     context: Optional[Dict[str, Any]] = None,
# ) -> List[str]:
#     """
#     Returns a list of human-readable violations. Empty list means ✅.
#     Expected plan shape:
#       { id, title, env, steps: [{action_type, description, command, service, ...}], predicted_impact: {...} }
#     """
#     violations: List[str] = []
#     env = (plan.get("env") or "prod").lower()
#     steps = plan.get("steps") or []

#     # Rule 1: Write/Mutation actions require approval for this incident
#     risky = {"config_change", "script", "db_migration", "restart", "scale"}
#     if any((s.get("action_type") in risky) for s in steps):
#         approved = bool(store.APPROVALS.get(incident_id))
#         if not approved:
#             violations.append("Write actions require approval for this incident.")

#     # Rule 2: No global feature-flag disable in prod
#     for s in steps:
#         txt = (s.get("description","") + " " + s.get("command","")).lower()
#         if "feature flag" in txt and "disable" in txt and env in PROD_ENVS:
#             violations.append("Global feature flag disable is not allowed in prod.")

#     # Rule 3: No DB schema changes without explicit backup step
#     if any(s.get("action_type") == "db_migration" for s in steps) and not _has_backup_step(steps):
#         violations.append("DB schema change without a preceding backup step.")

#     # Rule 4: No restarts of critical services during peak hours
#     if _is_peak() and any(s.get("action_type") == "restart" for s in steps):
#         violations.append("Service restarts are blocked during peak hours.")

#     # Rule 5: Env allowlist
#     allowlist = set((os.getenv("ENV_ALLOWLIST", "dev,staging,prod")).split(","))
#     if env not in allowlist:
#         violations.append(f"Target environment '{env}' is not in allowlist {sorted(allowlist)}.")

#     # Rule 6: Blast radius (no wildcard service target)
#     for s in steps:
#         if s.get("service") in ("*", "all", "global"):
#             violations.append("Steps must target a specific service; wildcard not allowed.")

#     return violations



# backend/app/policy/policy_guard.py
from __future__ import annotations
import os
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Dict, List, Optional

# ---------- Tunables (env) ----------
ENV_ALLOWLIST = {s.strip().lower() for s in os.getenv("ENV_ALLOWLIST", "dev,staging,prod").split(",") if s.strip()}
PROD_ENVS     = {s.strip().lower() for s in os.getenv("PROD_ENVS", "prod,production").split(",") if s.strip()}

PEAK_START = os.getenv("PEAK_START", "09:00:00")
PEAK_END   = os.getenv("PEAK_END",   "21:00:00")

REQUIRE_APPROVAL_FOR_WRITES   = os.getenv("REQUIRE_APPROVAL_FOR_WRITES", "1") == "1"
BLOCK_GLOBAL_FF_IN_PROD       = os.getenv("BLOCK_GLOBAL_FF_IN_PROD", "1") == "1"
REQUIRE_BACKUP_FOR_SCHEMA     = os.getenv("REQUIRE_BACKUP_FOR_SCHEMA", "1") == "1"
MAX_TARGETS_PROD              = int(os.getenv("MAX_TARGETS_PROD", "5"))

SENSITIVE_SERVICES = {s.strip().lower() for s in os.getenv("SENSITIVE_SERVICES", "auth,payments").split(",") if s.strip()}

# Action types we recognize
READ_ONLY   = {"read", "observe"}
WRITE_TYPES = {"config_change", "db_schema", "restart", "deploy", "feature_flag", "scale", "rollback"}

def _parse_clock(s: str) -> time:
    h, m, sec = (int(x) for x in s.split(":"))
    return time(h, m, sec)

PEAK_START_T = _parse_clock(PEAK_START)
PEAK_END_T   = _parse_clock(PEAK_END)

def _in_peak(now: Optional[datetime] = None) -> bool:
    now = now or datetime.utcnow()
    t = now.time()
    if PEAK_START_T <= PEAK_END_T:
        return PEAK_START_T <= t <= PEAK_END_T
    else:  # overnight window (e.g., 22:00–06:00)
        return t >= PEAK_START_T or t <= PEAK_END_T

@dataclass
class Violation:
    code: str
    message: str

def _violation(code: str, msg: str) -> Dict[str, str]:
    return {"code": code, "message": msg}

def evaluate_step(step: Dict[str, Any], approved: bool, now: Optional[datetime] = None) -> List[Dict[str, str]]:
    """
    Returns a list of violations for a single step.
    Expected step fields (best-effort): action_type, env, service, targets, op, key, backup_id
    """
    v: List[Dict[str, str]] = []
    action = str(step.get("action_type") or "").lower() or "read"
    env    = str(step.get("env") or "dev").lower()
    svc    = str(step.get("service") or "").strip().lower()
    targets = step.get("targets") or []
    if isinstance(targets, str):
        targets = [targets]

    # Env allowlist
    if env not in ENV_ALLOWLIST:
        v.append(_violation("env_not_allowlisted", f"env '{env}' not in allowlist {sorted(ENV_ALLOWLIST)}"))

    # Approval for writes (any env)
    if REQUIRE_APPROVAL_FOR_WRITES and (action in WRITE_TYPES) and not approved:
        v.append(_violation("approval_required", f"write action '{action}' requires approval"))

    # Wildcard service
    if svc in {"*", "all"}:
        v.append(_violation("wildcard_service_blocked", "wildcard service not allowed"))

    # Sensitive services are stricter (writes must be approved)
    if svc in SENSITIVE_SERVICES and (action in WRITE_TYPES) and not approved:
        v.append(_violation("sensitive_requires_approval", f"writes on sensitive service '{svc}' require approval"))

    # Peak-time restrictions (prod only)
    if env in PROD_ENVS and _in_peak(now) and action in {"restart", "deploy"}:
        v.append(_violation("blocked_in_peak", f"'{action}' blocked during peak window {PEAK_START}-{PEAK_END} in {env}"))

    # DB schema changes require a backup reference
    if action == "db_schema" and REQUIRE_BACKUP_FOR_SCHEMA and not step.get("backup_id"):
        v.append(_violation("backup_required", "db schema changes require 'backup_id'"))

    # Feature flag safety in prod: block global disable
    if env in PROD_ENVS and action == "feature_flag":
        op  = str(step.get("op") or "").lower()
        key = str(step.get("key") or "").lower()
        if BLOCK_GLOBAL_FF_IN_PROD and op in {"disable", "off"} and key in {"*", "all"}:
            v.append(_violation("global_ff_disable_blocked", "disabling ALL feature flags in prod is blocked"))

    # Blast radius in prod
    if env in PROD_ENVS:
        if targets == ["*"] or len(targets) > MAX_TARGETS_PROD:
            v.append(_violation("excessive_blast_radius", f"targets {targets} exceed prod limit ({MAX_TARGETS_PROD})"))

    return v

def evaluate_plan(plan: Dict[str, Any], approved: bool, now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Evaluate all steps and summarize.
    Returns: {"policy_ok": bool, "policy_violations": [..], "violations_by_step": {...}}
    """
    steps = plan.get("steps") or []
    all_violations: List[Dict[str, str]] = []
    by_step: List[List[Dict[str, str]]] = []

    for s in steps:
        vs = evaluate_step(s, approved=approved, now=now)
        by_step.append(vs)
        all_violations.extend(vs)

    return {
        "policy_ok": len(all_violations) == 0,
        "policy_violations": all_violations,
        "violations_by_step": by_step,
    }
