# app/models/sql.py
from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Any

from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from app.core.db import Base


class IncidentORM(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    service: Mapped[str] = mapped_column(String, index=True)
    severity: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String, index=True, default="OPEN")
    suspected_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Store lists (of dicts) as JSONB
    signals: Mapped[Optional[List[Any]]] = mapped_column(JSONB, nullable=True)
    evidence: Mapped[Optional[List[Any]]] = mapped_column(JSONB, nullable=True)
    remediation_candidates: Mapped[Optional[List[Any]]] = mapped_column(JSONB, nullable=True)
    validation_results: Mapped[Optional[List[Any]]] = mapped_column(JSONB, nullable=True)
