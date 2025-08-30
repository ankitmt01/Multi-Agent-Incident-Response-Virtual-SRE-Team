# app/services/policy_guard.py
from __future__ import annotations
from typing import Set, Iterable, Any, Dict
from app.core.config import get_settings

def _csv_set(s: str | None) -> Set[str]:
    if not s:
        return set()
    return {t.strip().lower() for t in s.split(",") if t.strip()}

class PolicyGuard:
    """
    Simple, declarative-ish policy:
      - actions in high_risk_actions_csv  -> blocked
      - actions in needs_approval_actions_csv -> needs_approval
      - otherwise allowed (with non-prod note if env in nonprod_envs_csv)
    """
    def __init__(self) -> None:
        s = get_settings()
        self._high_risk = _csv_set(getattr(s, "high_risk_actions_csv", ""))
        self._needs_approval = _csv_set(getattr(s, "needs_approval_actions_csv", ""))
        self._nonprod_envs = _csv_set(getattr(s, "nonprod_envs_csv", "dev,staging"))
        self._allow_manual = bool(getattr(s, "allow_manual_approval", True))
        self._env = (getattr(s, "app_env", "dev") or "dev").lower()

    def evaluate_action(self, action_name: str) -> Dict[str, Any]:
        """
        Returns: {"status": "allowed"|"needs_approval"|"blocked", "reasons": [..]}
        """
        name = (action_name or "").strip().lower()
        reasons: list[str] = []

        if name in self._high_risk:
            reasons.append("Action is listed as high risk")
            return {"status": "blocked", "reasons": reasons}

        if name in self._needs_approval:
            reasons.append("Action requires approval")
            return {"status": "needs_approval", "reasons": reasons}

        if self._env in self._nonprod_envs:
            reasons.append(f"Environment '{self._env}' considered non-prod")

        return {"status": "allowed", "reasons": reasons}

    def enforce(self, candidates: Iterable[Any], env: str = "") -> None:
        """
        Mutates candidate.policy_status / candidate.policy_reasons in-place.
        Supports both Pydantic objects and dict-like candidates.
        """
        _env = (env or self._env or "dev").lower()
        for c in candidates or []:
            name = getattr(c, "name", None) or (c.get("name") if isinstance(c, dict) else None) or ""
            verdict = self.evaluate_action(name)
            status = verdict["status"]
            reasons = verdict.get("reasons", [])
            # write back
            if isinstance(c, dict):
                c["policy_status"] = status
                c.setdefault("policy_reasons", []).extend(reasons)
            else:
                setattr(c, "policy_status", status)
                cur = list(getattr(c, "policy_reasons", []) or [])
                setattr(c, "policy_reasons", cur + reasons)

    def allow_manual(self) -> bool:
        return self._allow_manual
