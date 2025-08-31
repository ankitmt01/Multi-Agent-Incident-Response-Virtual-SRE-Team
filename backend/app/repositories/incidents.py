from __future__ import annotations

import secrets
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.common import Severity
from app.models.incident import (
    Incident,
    IncidentSignal,
    EvidenceItem,
    RemediationCandidate,
    ValidationResult,
)
from app.models.sql import (
    IncidentORM,
    IncidentSignalORM,
    EvidenceItemORM,
    RemediationCandidateORM,
    ValidationResultORM,
)


# ----------------- helpers -----------------
def _to_pyd(orm: IncidentORM) -> Incident:
    # map DB string -> pydantic enum (or None)
    sev_enum = Severity(orm.severity) if orm.severity else None

    return Incident(
        id=orm.id,
        service=orm.service,
        severity=sev_enum,
        created_at=orm.created_at,
        suspected_cause=orm.suspected_cause,
        status=orm.status,
        signals=[
            IncidentSignal(
                source=s.source,
                label=s.label,
                value=s.value,
                unit=s.unit,
                window_s=s.window_s,
                at=s.at,
            )
            for s in (orm.signals or [])
        ],
        evidence=[
            EvidenceItem(
                title=e.title,
                content=e.content,
                score=e.score,
                uri=e.uri,
            )
            for e in (orm.evidence or [])
        ],
        remediation_candidates=[
            RemediationCandidate(
                name=c.name,
                steps=c.steps,
                risks=c.risks,
                rollback=c.rollback,
                rationale=c.rationale,
                predicted_impact=c.predicted_impact,
                actions=c.actions,
                policy_status=c.policy_status,
                policy_reasons=c.policy_reasons,
            )
            for c in (orm.candidates or [])
        ],
        validation_results=[
            ValidationResult(
                candidate=v.candidate,
                passed=v.passed,
                notes=v.notes,
                kpi_before=v.kpi_before,
                kpi_after=v.kpi_after,
            )
            for v in (orm.validations or [])
        ],
    )


def _ensure_id(inc: Incident) -> None:
    if not inc.id or not inc.id.strip():
        inc.id = secrets.token_hex(16)  # 32-char hex


# ----------------- repository -----------------
class IncidentRepository:
    async def get_all(self, session: AsyncSession) -> List[Incident]:
        q = select(IncidentORM)
        res = await session.execute(q)
        rows = res.scalars().unique().all()
        return [_to_pyd(r) for r in rows]

    async def get_many(self, session: AsyncSession) -> List[Incident]:
        # alias used by some callers
        return await self.get_all(session)

    async def get_one(self, session: AsyncSession, incident_id: str) -> Optional[Incident]:
        row = await session.get(IncidentORM, incident_id)
        return _to_pyd(row) if row else None

    async def upsert(self, session: AsyncSession, inc: Incident) -> Incident:
        """
        Persist the Incident and all children (replace-on-write).
        NOTE: severity is stored as TEXT in DB; we map enum<->str here.
        """
        _ensure_id(inc)

        header = await session.get(IncidentORM, inc.id)
        if not header:
            header = IncidentORM(id=inc.id, service=inc.service)
            session.add(header)
        else:
            header.service = inc.service

        # enum -> str (or None)
        header.severity = inc.severity.value if inc.severity else None
        header.created_at = inc.created_at
        header.suspected_cause = inc.suspected_cause
        header.status = inc.status

        # wipe children, then re-add
        await session.execute(delete(IncidentSignalORM).where(IncidentSignalORM.incident_id == inc.id))
        await session.execute(delete(EvidenceItemORM).where(EvidenceItemORM.incident_id == inc.id))
        await session.execute(delete(RemediationCandidateORM).where(RemediationCandidateORM.incident_id == inc.id))
        await session.execute(delete(ValidationResultORM).where(ValidationResultORM.incident_id == inc.id))

        for s in inc.signals or []:
            session.add(
                IncidentSignalORM(
                    incident_id=inc.id,
                    source=s.source,
                    label=s.label,
                    value=s.value,
                    unit=s.unit,
                    window_s=s.window_s,
                    at=s.at,
                )
            )

        for e in inc.evidence or []:
            session.add(
                EvidenceItemORM(
                    incident_id=inc.id,
                    title=e.title,
                    content=e.content,
                    score=e.score,
                    uri=e.uri,
                )
            )

        for c in inc.remediation_candidates or []:
            session.add(
                RemediationCandidateORM(
                    incident_id=inc.id,
                    name=c.name,
                    steps=c.steps,
                    risks=c.risks,
                    rollback=c.rollback,
                    rationale=c.rationale,
                    predicted_impact=c.predicted_impact,
                    actions=c.actions,
                    policy_status=c.policy_status,
                    policy_reasons=c.policy_reasons,
                )
            )

        for v in inc.validation_results or []:
            session.add(
                ValidationResultORM(
                    incident_id=inc.id,
                    candidate=v.candidate,
                    passed=v.passed,
                    notes=v.notes,
                    kpi_before=v.kpi_before,
                    kpi_after=v.kpi_after,
                )
            )

        await session.commit()
        await session.refresh(header)
        return _to_pyd(header)

    # backwards-compat name used by your router
    async def create_or_overwrite(self, session: AsyncSession, inc: Incident) -> Incident:
        return await self.upsert(session, inc)


# ------------- module-level helpers (keep old imports working) -------------
_repo = IncidentRepository()

async def get_all(session: AsyncSession) -> List[Incident]:
    return await _repo.get_all(session)

async def get_many(session: AsyncSession) -> List[Incident]:
    return await _repo.get_many(session)

async def get_one(session: AsyncSession, incident_id: str) -> Optional[Incident]:
    return await _repo.get_one(session, incident_id)

async def create_or_overwrite(session: AsyncSession, inc: Incident) -> Incident:
    return await _repo.create_or_overwrite(session, inc)
