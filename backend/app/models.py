from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
import uuid

class Signal(BaseModel):
    name: str
    value: float
    unit: str = ""
    window_s: int = 60

class DetectRequest(BaseModel):
    service: str
    signals: List[Signal]
    suspected_cause: Optional[str] = None

class Incident(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    severity: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    suspected_cause: Optional[str] = None
    notes: Dict[str, str] = {}

class EvidenceItem(BaseModel):
    title: str
    snippet: str
    score: float
    uri: str
    source_file: str

class CandidateStep(BaseModel):
    action: str
    action_type: str  # read|config_change|write
    details: Dict[str, str] = {}

class CandidatePlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    rationale: str
    predicted_impact: str
    steps: List[CandidateStep]
    policy_violations: List[str] = []
    approved: bool = False

class ValidationResult(BaseModel):
    before: Dict[str, float]
    after: Dict[str, float]
    kpi_deltas: Dict[str, float]
    status: str  # PASS|FAIL

class PipelineResult(BaseModel):
    evidence: List[EvidenceItem]
    candidates: List[CandidatePlan]
    validation: Optional[ValidationResult] = None
    policy_summary: str = ""
