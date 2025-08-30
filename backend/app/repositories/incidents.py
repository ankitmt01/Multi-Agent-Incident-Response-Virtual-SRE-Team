# backend/app/repositories/incidents.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import Table, Column, String, DateTime, select
from sqlalchemy.dialects.postgresql import JSONB, insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import metadata as core_metadata
from app.models.incident import Incident


# SQLAlchemy table mapping (no create_all here; your Alembic migration owns the schema)
incidents_table = Table(
    "incidents",
    core_metadata,
    Column("id", String, primary_key=True),
    Column("service", String, nullable=False),
    Column("severity", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("status", String, nullable=False),
    Column("suspected_cause", String, nullable=True),
    Column("signals", JSONB, nullable=False),
    Column("evidence", JSONB, nullable=False),
    Column("remediation_candidates", JSONB, nullable=False),
    Column("validation_results", JSONB, nullable=False),
)


def _payload_for_db(incident: Incident) -> dict:
    """
    Build a DB-friendly dict:
    - Use JSON mode for nested JSONB fields so everything is JSON-serializable.
    - Force created_at to a real timezone-aware datetime for the TIMESTAMPTZ column.
    """
    data = incident.model_dump(mode="json", exclude_none=True)

    # Ensure created_at is a datetime for Postgres TIMESTAMPTZ
    dt = incident.created_at
    if isinstance(dt, str):
        # Accept ISO strings if they ever appear
        dt = datetime.fromisoformat(dt)
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        data["created_at"] = dt
    else:
        # Fallback: set to "now" in UTC if missing or malformed
        data["created_at"] = datetime.now(timezone.utc)

    # Guarantee arrays exist for JSONB columns to avoid NULL issues
    data.setdefault("signals", [])
    data.setdefault("evidence", [])
    data.setdefault("remediation_candidates", [])
    data.setdefault("validation_results", [])

    # Guarantee id exists (Incident typically has one, but just in case)
    if not data.get("id"):
        # simple deterministic-ish id if none present
        data["id"] = f"INC-{datetime.now(timezone.utc).strftime('%H%M%S%f')[:8].upper()}"

    return data


def _row_to_model(row) -> Incident:
    # row is a RowMapping; convert to dict and let Pydantic coerce nested JSON into typed models
    return Incident.model_validate(dict(row))


class IncidentRepository:
    """Async repository for incidents."""

    async def list(self, db: AsyncSession, *, limit: int = 50, offset: int = 0) -> List[Incident]:
        stmt = (
            select(incidents_table)
            .order_by(incidents_table.c.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await db.execute(stmt)
        rows = res.mappings().all()
        return [_row_to_model(r) for r in rows]

    async def get(self, db: AsyncSession, incident_id: str) -> Optional[Incident]:
        stmt = select(incidents_table).where(incidents_table.c.id == incident_id)
        res = await db.execute(stmt)
        row = res.mappings().one_or_none()
        return _row_to_model(row) if row else None

    async def upsert(self, db: AsyncSession, incident: Incident) -> Incident:
        """
        Postgres ON CONFLICT(id) DO UPDATE … upsert.
        Keeps 'created_at' as a datetime; JSONB fields are proper JSON.
        """
        data = _payload_for_db(incident)

        # Columns to update on conflict (don't update primary key or created_at by default)
        update_cols = {
            k: getattr(pg_insert(incidents_table).excluded, k)
            for k in (
                "service",
                "severity",
                "status",
                "suspected_cause",
                "signals",
                "evidence",
                "remediation_candidates",
                "validation_results",
            )
        }

        stmt = (
            pg_insert(incidents_table)
            .values(**data)
            .on_conflict_do_update(
                index_elements=[incidents_table.c.id],
                set_=update_cols,
            )
            .returning(incidents_table)
        )
        res = await db.execute(stmt)
        row = res.mappings().one()
        return _row_to_model(row)
