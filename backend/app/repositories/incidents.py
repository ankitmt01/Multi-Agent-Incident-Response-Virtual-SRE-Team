from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sql import (
    IncidentORM, IncidentSignalORM, EvidenceItemORM,
    RemediationCandidateORM, ValidationResultORM,
)
from app.models.incident import (
    Incident, IncidentSignal, EvidenceItem,
    RemediationCandidate, ValidationResult,
)

# Ensure DB gets a naive-UTC datetime (column is timezone=False)
def _naive_utc(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return datetime.utcnow()
    if dt.tzinfo is None:
        return dt  # assume already naive UTC for this app
    return dt.astimezone(timezone.utc).replace(tzinfo=None)

def _sev_to_str(val) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, PyEnum):
        return str(val.value)
    return str(val)

def _to_pyd(orm: IncidentORM) -> Incident:
    return Incident(
        id=orm.id,
        service=orm.service,
        severity=orm.severity,  # stored as plain string
        created_at=orm.created_at,
        suspected_cause=orm.suspected_cause,
        status=orm.status,
        signals=[
            IncidentSignal(
                source=s.source, label=s.label, value=s.value,
                unit=s.unit, window_s=s.window_s, at=s.at
            ) for s in (orm.signals or [])
        ],
        evidence=[
            EvidenceItem(
                title=e.title, content=e.content, score=e.score, uri=e.uri
            ) for e in (orm.evidence or [])
        ],
        remediation_candidates=[
            RemediationCandidate(
                name=c.name, steps=c.steps, risks=c.risks, rollback=c.rollback,
                rationale=c.rationale, predicted_impact=c.predicted_impact,
                actions=c.actions, policy_status=c.policy_status, policy_reasons=c.policy_reasons
            ) for c in (orm.candidates or [])
        ],
        validation_results=[
            ValidationResult(
                candidate=v.candidate, passed=v.passed, notes=v.notes,
                kpi_before=v.kpi_before, kpi_after=v.kpi_after
            ) for v in (orm.validations or [])
        ],
    )

# ---------- free functions ----------

async def get_many(session: AsyncSession) -> List[Incident]:
    res = await session.execute(select(IncidentORM))
    rows = res.scalars().unique().all()
    return [_to_pyd(r) for r in rows]

async def get_one(session: AsyncSession, incident_id: str) -> Optional[Incident]:
    row = await session.get(IncidentORM, incident_id)
    return _to_pyd(row) if row else None

async def create_or_overwrite(session: AsyncSession, inc: Incident) -> Incident:
    header = await session.get(IncidentORM, inc.id)
    if not header:
        header = IncidentORM(id=inc.id, service=inc.service)
        session.add(header)

    header.severity = _sev_to_str(inc.severity)
    header.created_at = _naive_utc(inc.created_at)
    header.suspected_cause = inc.suspected_cause
    header.status = inc.status or "OPEN"

    # wipe children
    await session.execute(delete(IncidentSignalORM).where(IncidentSignalORM.incident_id == inc.id))
    await session.execute(delete(EvidenceItemORM).where(EvidenceItemORM.incident_id == inc.id))
    await session.execute(delete(RemediationCandidateORM).where(RemediationCandidateORM.incident_id == inc.id))
    await session.execute(delete(ValidationResultORM).where(ValidationResultORM.incident_id == inc.id))

    # re-add children
    for s in inc.signals or []:
        session.add(IncidentSignalORM(
            incident_id=inc.id, source=s.source, label=s.label, value=s.value,
            unit=s.unit, window_s=s.window_s, at=_naive_utc(getattr(s, "at", None))
        ))
    for e in inc.evidence or []:
        session.add(EvidenceItemORM(
            incident_id=inc.id, title=e.title, content=e.content, score=e.score, uri=e.uri
        ))
    for c in inc.remediation_candidates or []:
        session.add(RemediationCandidateORM(
            incident_id=inc.id, name=c.name, steps=c.steps, risks=c.risks, rollback=c.rollback,
            rationale=c.rationale, predicted_impact=c.predicted_impact, actions=c.actions,
            policy_status=c.policy_status, policy_reasons=c.policy_reasons
        ))
    for v in inc.validation_results or []:
        session.add(ValidationResultORM(
            incident_id=inc.id, candidate=v.candidate, passed=v.passed, notes=v.notes,
            kpi_before=v.kpi_before, kpi_after=v.kpi_after
        ))

    await session.commit()
    await session.refresh(header)
    return _to_pyd(header)

# ---------- thin class shim for demo.py ----------

class IncidentRepository:
    async def get_many(self, session: AsyncSession) -> List[Incident]:
        return await get_many(session)

    async def get_one(self, session: AsyncSession, incident_id: str) -> Optional[Incident]:
        return await get_one(session, incident_id)

    async def upsert(self, session: AsyncSession, inc: Incident) -> Incident:
        return await create_or_overwrite(session, inc)
