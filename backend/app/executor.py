





from __future__ import annotations
from typing import Any, Dict, List, Optional
from datetime import datetime
import time

from .policy.policy_guard import evaluate_plan
from .audit import write_event


HARD_BLOCKS = {
    "env_not_allowlisted",
    "wildcard_service_blocked",
    "global_ff_disable_blocked",
    "excessive_blast_radius",
    "blocked_in_peak",
    "backup_required",
}

def _utcnow_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

def _sleep_ms(ms: int):

    time.sleep(min(ms, 50) / 1000.0)

def _ok(msg: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out = {"ok": True, "message": msg}
    if extra:
        out.update(extra)
    return out

def _err(msg: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out = {"ok": False, "message": msg}
    if extra:
        out.update(extra)
    return out


def _exec_read(step: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
  
    return _ok("read-only observation", {"sample": {"status": "healthy"}})

def _exec_config_change(step: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    key = step.get("key")
    value = step.get("value")
    if not key:
        return _err("missing 'key' for config_change")
    if dry_run:
        return _ok(f"would change config {key} -> {value!r}")
     # TODO: 
    return _ok(f"changed config {key} -> {value!r}")

def _exec_restart(step: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    targets = step.get("targets") or []
    if not targets:
        return _err("restart requires non-empty 'targets'")
    if dry_run:
        return _ok(f"would restart {targets}")
    return _ok(f"restarted {targets}")

def _exec_deploy(step: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    version = step.get("version", "latest")
    targets = step.get("targets") or []
    if not targets:
        return _err("deploy requires non-empty 'targets'")
    if dry_run:
        return _ok(f"would deploy {version} to {targets}")
    return _ok(f"deployed {version} to {targets}")

def _exec_feature_flag(step: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    key = step.get("key")
    op  = (step.get("op") or "").lower()  # enable/disable/on/off/percent
    if not key or not op:
        return _err("feature_flag requires 'key' and 'op'")
    if dry_run:
        return _ok(f"would set feature '{key}' -> {op}")
    return _ok(f"feature '{key}' -> {op}")

def _exec_db_schema(step: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if not step.get("backup_id"):
        return _err("db_schema requires 'backup_id' (policy also enforces this)")
    change = step.get("change", "migration")
    if dry_run:
        return _ok(f"would apply schema change '{change}' (backup {step['backup_id']})")
    return _ok(f"applied schema change '{change}' (backup {step['backup_id']})")

def _exec_scale(step: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    targets = step.get("targets") or []
    replicas = step.get("replicas")
    if not targets or replicas is None:
        return _err("scale requires 'targets' and 'replicas'")
    if dry_run:
        return _ok(f"would scale {targets} to {replicas} replicas")
    return _ok(f"scaled {targets} to {replicas} replicas")

def _exec_rollback(step: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    target = (step.get("targets") or ["service"])[0]
    if dry_run:
        return _ok(f"would rollback {target} to previous version")
    return _ok(f"rolled back {target} to previous version")

STEP_HANDLERS = {
    "read": _exec_read,
    "observe": _exec_read,
    "config_change": _exec_config_change,
    "restart": _exec_restart,
    "deploy": _exec_deploy,
    "feature_flag": _exec_feature_flag,
    "db_schema": _exec_db_schema,
    "scale": _exec_scale,
    "rollback": _exec_rollback,
}

def _execute_step(idx: int, step: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    started = _utcnow_iso()
    action = (step.get("action_type") or "read").lower()
    handler = STEP_HANDLERS.get(action)
    if not handler:
        res = _err(f"unsupported action_type '{action}'")
    else:
        _sleep_ms(20)
        res = handler(step, dry_run=dry_run)
    ended = _utcnow_iso()
    res.update({
        "step_index": idx,
        "action_type": action,
        "started_at": started,
        "ended_at": ended,
    })
    return res

def execute_plan(incident, plan: Dict[str, Any], approved: bool, dry_run: bool = True) -> Dict[str, Any]:
    """
    Execute a remediation plan step-by-step.
    - Re-evaluates policy at execution time.
    - If violations contain hard blocks, refuse to execute.
    - If write actions but not approved, refuse to execute.
    - Returns a structured result with per-step details.
    """
    exec_id = f"exec-{getattr(incident, 'id', 'inc')[:8]}-{(plan.get('id') or 'plan')[:12]}"
    started = _utcnow_iso()

    # Re-evaluate policy snapshot
    pol = evaluate_plan(plan, approved=approved)
    violations: List[Dict[str, str]] = pol.get("policy_violations") or []
    hard = [v for v in violations if v.get("code") in HARD_BLOCKS]

    if hard:
        write_event("execute_blocked", {
            "incident_id": getattr(incident, "id", None),
            "plan_id": plan.get("id"),
            "reason": "hard_policy_block",
            "violations": hard,
        })
        return {
            "execution_id": exec_id,
            "incident_id": getattr(incident, "id", None),
            "plan_id": plan.get("id"),
            "status": "blocked",
            "blocked_by": [v.get("code") for v in hard],
            "policy_snapshot": pol,
            "dry_run": dry_run,
            "started_at": started,
            "ended_at": _utcnow_iso(),
            "steps": [],
        }

    if not pol.get("policy_ok") and not approved:
        write_event("execute_blocked", {
            "incident_id": getattr(incident, "id", None),
            "plan_id": plan.get("id"),
            "reason": "approval_required",
            "violations": violations,
        })
        return {
            "execution_id": exec_id,
            "incident_id": getattr(incident, "id", None),
            "plan_id": plan.get("id"),
            "status": "blocked",
            "blocked_by": [v.get("code") for v in violations],
            "policy_snapshot": pol,
            "dry_run": dry_run,
            "started_at": started,
            "ended_at": _utcnow_iso(),
            "steps": [],
        }

    steps = plan.get("steps") or []
    step_results: List[Dict[str, Any]] = []
    overall_ok = True

    write_event("execute_start", {
        "incident_id": getattr(incident, "id", None),
        "plan_id": plan.get("id"),
        "dry_run": dry_run,
        "step_count": len(steps),
    })

    for i, step in enumerate(steps):
        write_event("execute_step_begin", {
            "incident_id": getattr(incident, "id", None),
            "plan_id": plan.get("id"),
            "index": i,
            "action_type": step.get("action_type"),
        })
        res = _execute_step(i, step, dry_run=dry_run)
        step_results.append(res)
        write_event("execute_step_end", {
            "incident_id": getattr(incident, "id", None),
            "plan_id": plan.get("id"),
            "index": i,
            "ok": bool(res.get("ok")),
            "message": res.get("message"),
        })
        if not res.get("ok"):
            overall_ok = False
 
            break

    ended = _utcnow_iso()
    status = "success" if overall_ok else "failed"

    write_event("execute_end", {
        "incident_id": getattr(incident, "id", None),
        "plan_id": plan.get("id"),
        "status": status,
    })

    return {
        "execution_id": exec_id,
        "incident_id": getattr(incident, "id", None),
        "plan_id": plan.get("id"),
        "status": status,
        "dry_run": dry_run,
        "policy_snapshot": pol,
        "steps": step_results,
        "started_at": started,
        "ended_at": ended,
    }
