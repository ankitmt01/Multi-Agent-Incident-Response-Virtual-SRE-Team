from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from .common import Severity

class IncidentSignal(BaseModel):
    source: str                 # "metrics" | "logs" | "alert"
    label: str                  # e.g., "http_5xx_rate", "latency_p95"
    value: float
    unit: Optional[str] = None  # e.g., "ms", "percent", "rps"
    window_s: Optional[int] = None
    at: datetime = Field(default_factory=datetime.utcnow)

class EvidenceItem(BaseModel):
    title: str
    content: str
    score: float = 0.0
    uri: Optional[str] = None

class RemediationCandidate(BaseModel):
    name: str
    steps: List[str]
    risks: List[str] = Field(default_factory=list)
    rollback: List[str] = Field(default_factory=list)
    rationale: str = ""
    predicted_impact: Dict[str, Any] = Field(default_factory=dict)
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    # Policy Guard outputs
    policy_status: str = "unknown"               # allowed | needs_approval | blocked | unknown
    policy_reasons: List[str] = Field(default_factory=list)

class ValidationResult(BaseModel):
    candidate: str
    passed: bool
    notes: str = ""
    kpi_before: Dict[str, float] = Field(default_factory=dict)
    kpi_after: Dict[str, float] = Field(default_factory=dict)

class Incident(BaseModel):
    id: Optional[str] = None
    service: str
    severity: Optional[Severity] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    signals: List[IncidentSignal] = Field(default_factory=list)
    suspected_cause: Optional[str] = None
    evidence: List[EvidenceItem] = Field(default_factory=list)
    remediation_candidates: List[RemediationCandidate] = Field(default_factory=list)
    validation_results: List[ValidationResult] = Field(default_factory=list)
    status: str = "OPEN"  # OPEN | TRIAGED | FIXED | FAILED
