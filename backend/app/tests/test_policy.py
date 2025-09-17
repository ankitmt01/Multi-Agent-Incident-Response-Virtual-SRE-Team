# backend/app/tests/test_policy.py
import os
from datetime import datetime
from app.policy.policy_guard import evaluate_plan

def _plan(action_type, env="prod", service="checkout", **kw):
    step = {"action_type": action_type, "env": env, "service": service}
    step.update(kw)
    return {"steps": [step]}

def test_requires_approval_for_writes(monkeypatch):
    monkeypatch.setenv("REQUIRE_APPROVAL_FOR_WRITES", "1")
    plan = _plan("config_change", env="staging")
    r = evaluate_plan(plan, approved=False, now=datetime(2025, 1, 1, 10, 0, 0))
    assert not r["policy_ok"]
    assert any(v["code"] == "approval_required" for v in r["policy_violations"])

def test_block_global_ff_disable_in_prod(monkeypatch):
    monkeypatch.setenv("BLOCK_GLOBAL_FF_IN_PROD", "1")
    plan = _plan("feature_flag", env="prod", key="*", op="disable")
    r = evaluate_plan(plan, approved=True, now=datetime(2025, 1, 1, 10, 0, 0))
    assert not r["policy_ok"]
    assert any(v["code"] == "global_ff_disable_blocked" for v in r["policy_violations"])

def test_db_schema_requires_backup(monkeypatch):
    monkeypatch.setenv("REQUIRE_BACKUP_FOR_SCHEMA", "1")
    plan = _plan("db_schema", env="staging")  # no backup_id
    r = evaluate_plan(plan, approved=True)
    assert not r["policy_ok"]
    assert any(v["code"] == "backup_required" for v in r["policy_violations"])

def test_restart_blocked_in_peak(monkeypatch):
    # Peak 09:00–21:00, now=10:00
    monkeypatch.setenv("PEAK_START", "09:00:00")
    monkeypatch.setenv("PEAK_END",   "21:00:00")
    plan = _plan("restart", env="prod")
    r = evaluate_plan(plan, approved=True, now=datetime(2025, 1, 1, 10, 0, 0))
    assert not r["policy_ok"]
    assert any(v["code"] == "blocked_in_peak" for v in r["policy_violations"])

def test_env_allowlist(monkeypatch):
    monkeypatch.setenv("ENV_ALLOWLIST", "dev,staging,prod")
    plan = _plan("read", env="qa")
    r = evaluate_plan(plan, approved=True)
    assert not r["policy_ok"]
    assert any(v["code"] == "env_not_allowlisted" for v in r["policy_violations"])
