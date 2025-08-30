from __future__ import annotations
from typing import Optional
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, ForeignKey, Enum, JSON, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

from app.core.db import Base
from app.models.common import Severity  # your existing enum

# Prefer JSONB on Postgres; fall back to JSON on SQLite
JSONType = JSONB().with_variant(JSON(), "sqlite")

class IncidentORM(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    service: Mapped[str] = mapped_column(String(200), index=True)
    severity: Mapped[Optional[Severity]] = mapped_column(Enum(Severity), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    suspected_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="OPEN")

    signals: Mapped[list["IncidentSignalORM"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan", lazy="selectin"
    )
    evidence: Mapped[list["EvidenceItemORM"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan", lazy="selectin"
    )
    candidates: Mapped[list["RemediationCandidateORM"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan", lazy="selectin"
    )
    validations: Mapped[list["ValidationResultORM"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan", lazy="selectin"
    )


class IncidentSignalORM(Base):
    __tablename__ = "incident_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(50))
    label: Mapped[str] = mapped_column(String(200))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    window_s: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)

    incident: Mapped[IncidentORM] = relationship(back_populates="signals")


class EvidenceItemORM(Base):
    __tablename__ = "incident_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    uri: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    incident: Mapped[IncidentORM] = relationship(back_populates="evidence")


class RemediationCandidateORM(Base):
    __tablename__ = "remediation_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    steps: Mapped[list[str]] = mapped_column(JSONType, default=list)
    risks: Mapped[list[str]] = mapped_column(JSONType, default=list)
    rollback: Mapped[list[str]] = mapped_column(JSONType, default=list)
    rationale: Mapped[str] = mapped_column(Text, default="")
    predicted_impact: Mapped[dict] = mapped_column(JSONType, default=dict)
    actions: Mapped[list[dict]] = mapped_column(JSONType, default=list)
    policy_status: Mapped[str] = mapped_column(String(32), default="unknown")
    policy_reasons: Mapped[list[str]] = mapped_column(JSONType, default=list)

    incident: Mapped[IncidentORM] = relationship(back_populates="candidates")


class ValidationResultORM(Base):
    __tablename__ = "validation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    candidate: Mapped[str] = mapped_column(String(200))
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    kpi_before: Mapped[dict] = mapped_column(JSONType, default=dict)
    kpi_after: Mapped[dict] = mapped_column(JSONType, default=dict)

    incident: Mapped[IncidentORM] = relationship(back_populates="validations")
