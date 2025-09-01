from __future__ import annotations

import csv
import os
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models.incident import Incident, IncidentSignal
from app.services.pipeline import PIPELINE

router = APIRouter(prefix="/demo", tags=["demo"])

# Repo: class-based preferred, function-based fallback
try:
    from app.repositories.incidents import IncidentRepository
    repo = IncidentRepository()
    _class_repo = True
except Exception:
    from app.repositories import incidents as repo  # function-style
    _class_repo = False


# ---------- seed metrics ----------
class SeedBody(BaseModel):
    service: str = "payments"
    minutes: int = 120


@router.post("/seed-metrics")
async def seed_metrics(body: SeedBody):
    service = body.service
    minutes = max(1, int(body.minutes))

    start = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    outdir = "/app/data/metrics"
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, f"{service}.csv")

    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "http_5xx_rate", "latency_p95_ms"])
        for m in range(minutes):
            ts = start + timedelta(minutes=m)
            # last ~10 minutes go “bad”
            rate = 12.0 if m >= minutes - 10 else 0.5
            p95 = 1200.0 if m >= minutes - 10 else 200.0
            w.writerow([ts.isoformat(), rate, p95])

    return {"ok": True, "path": path}
# ---------- /seed metrics ----------


# ---------- generate incidents ----------
class GenBody(BaseModel):
    service: str = "payments"
    count: int = 3
    run_pipeline: bool = True


def _new_id() -> str:
    import secrets
    return "INC-" + secrets.token_hex(4).upper()


@router.post("/generate-incidents")
async def generate_incidents(
    body: GenBody,
    db: AsyncSession = Depends(get_session),
):
    try:
        ids: List[str] = []
        for _ in range(max(1, body.count)):
            inc = Incident(
                id=_new_id(),
                service=body.service,
                severity=None,  # will be filled by detector or left null
                created_at=datetime.utcnow(),  # naive UTC to match DB column
                status="OPEN",
                suspected_cause="bad deploy",
                signals=[
                    IncidentSignal(source="metrics", label="http_5xx_rate", value=12.0, unit=None, window_s=300),
                    IncidentSignal(source="metrics", label="latency_p95", value=1200.0, unit="ms", window_s=300),
                ],
                evidence=[],
                remediation_candidates=[],
                validation_results=[],
            )

            # write once so it appears immediately
            if _class_repo and hasattr(repo, "upsert"):
                await repo.upsert(db, inc)
            else:
                await repo.create_or_overwrite(db, inc)  # type: ignore

            if body.run_pipeline:
                PIPELINE.run_all(inc)  # mutates inc in-place

                # ensure severity stored as string if enum-like
                if getattr(inc, "severity", None) is not None and not isinstance(inc.severity, str):
                    inc.severity = getattr(inc.severity, "value", str(inc.severity))

                if _class_repo and hasattr(repo, "upsert"):
                    await repo.upsert(db, inc)
                else:
                    await repo.create_or_overwrite(db, inc)  # type: ignore

            ids.append(inc.id)

        await db.commit()
        return {"ok": True, "ids": ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"demo error: {e}")
# ---------- /generate incidents ----------
