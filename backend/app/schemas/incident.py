from __future__ import annotations
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from ..models.incident import IncidentStatus

class IncidentCreate(BaseModel):
    title: str
    severity: int = 3
    tags: List[str] = Field(default_factory=list)
    evidence: Dict[str, Any] = Field(default_factory=dict)

class IncidentUpdate(BaseModel):
    title: Optional[str] = None
    severity: Optional[int] = None
    status: Optional[IncidentStatus] = None
    tags: Optional[List[str]] = None
    evidence: Optional[Dict[str, Any]] = None
    candidates: Optional[Dict[str, Any]] = None
    remediation: Optional[Dict[str, Any]] = None
    validation: Optional[Dict[str, Any]] = None
    report_md: Optional[str] = None

class IncidentOut(BaseModel):
    id: str
    title: str
    severity: int
    status: IncidentStatus
    tags: List[str]
    evidence: Dict[str, Any]
    candidates: Dict[str, Any]
    remediation: Dict[str, Any]
    validation: Dict[str, Any]
    report_md: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class IncidentEventCreate(BaseModel):
    kind: str
    payload: Dict[str, Any] = Field(default_factory=dict)

class IncidentEventOut(BaseModel):
    id: str
    incident_id: str
    at: datetime
    kind: str
    payload: Dict[str, Any]

    class Config:
        from_attributes = True
