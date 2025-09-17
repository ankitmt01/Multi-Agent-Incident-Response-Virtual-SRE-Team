from __future__ import annotations
from enum import Enum
from pydantic import BaseModel
from typing import Dict, Tuple


class Action(str, Enum):
ROLLBACK = "rollback"
SCALE_DB_POOL = "scale_db_pool"
CLEAR_CACHE = "clear_cache"


SEVERITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


class ActionRequest(BaseModel):
incident_id: str
action: Action
severity: str
environment: str = "prod"
dry_run: bool = True


POLICY = {
Action.ROLLBACK: {"min_severity": "MEDIUM", "require_approval": True},
Action.SCALE_DB_POOL:{"min_severity": "MEDIUM", "require_approval": True},
Action.CLEAR_CACHE: {"min_severity": "LOW", "require_approval": False},
}


def allowed(req: ActionRequest, approvals: Dict[str, bool]) -> Tuple[bool, str]:
rule = POLICY[req.action]
if SEVERITY_RANK.get(req.severity, 0) < SEVERITY_RANK[rule["min_severity"]]:
return False, f"severity {req.severity} below minimum {rule['min_severity']}"
if req.environment == "prod" and rule["require_approval"] and not approvals.get(req.incident_id, False):
return False, "approval required"
return True, "allowed"