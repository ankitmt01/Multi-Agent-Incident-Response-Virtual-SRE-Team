from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, JSON, Text
from ..core.db import Base

class IncidentORM(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    service: Mapped[str] = mapped_column(String(200))
    severity: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # store enum as string
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="OPEN")

    suspected_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # JSON blobs mirroring your Pydantic lists
    signals: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)                 # store as list in JSON
    evidence: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    remediation_candidates: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    validation_results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
