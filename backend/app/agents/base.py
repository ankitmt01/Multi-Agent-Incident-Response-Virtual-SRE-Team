from pydantic import BaseModel
from typing import Any, Optional
from ..models.incident import Incident
from ..models.common import AgentName

class AgentContext(BaseModel):
    incident: Incident
    settings: Any

class AgentResult(BaseModel):
    agent: AgentName
    ok: bool = True
    message: str = ""
    data: Any = None

class Agent:
    name: AgentName

    def run(self, ctx: AgentContext) -> AgentResult:
        raise NotImplementedError("Agent must implement run()")

