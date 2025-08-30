# app/api/routers/incident.py
from __future__ import annotations

import html as _html
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.core.db import get_session
from app.repositories.incidents import IncidentRepository
from app.models.incident import Incident
from app.services.pipeline import PIPELINE
from app.agents.base import AgentContext
from starlette.responses import StreamingResponse
from app.core.events import sse_stream, emit

router = APIRouter(prefix="/incidents", tags=["incidents"])
repo = IncidentRepository()


def _db_missing_table(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "no such table" in msg or ("relation" in msg and "does not exist" in msg)


@router.get("/", response_model=List[Incident])
async def list_incidents(limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_session)):
    try:
        return await repo.list(db, limit=limit, offset=offset)
    except (ProgrammingError, OperationalError) as e:
        if _db_missing_table(e):
            return []
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

# also accept /incidents (no trailing slash)
router.add_api_route(path="", endpoint=list_incidents, methods=["GET"], response_model=List[Incident])


@router.get("/{incident_id}", response_model=Incident)
async def get_incident(incident_id: str, db: AsyncSession = Depends(get_session)):
    try:
        inc = await repo.get(db, incident_id)
        if not inc:
            raise HTTPException(status_code=404, detail="Incident not found")
        return inc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.post("/detect", response_model=Incident)
async def detect_incident(incident: Incident, db: AsyncSession = Depends(get_session)):
    if not incident.signals:
        raise HTTPException(status_code=422, detail="signals must contain at least one item")

    ctx = AgentContext(incident=incident, settings=PIPELINE.settings)
    PIPELINE.detector.run(ctx)

    try:
        saved = await repo.upsert(db, incident)
        await db.commit()
        return saved
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.post("/{incident_id}/run")
async def run_pipeline(incident_id: str, db: AsyncSession = Depends(get_session)):
    inc = await repo.get(db, incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    # START
    await emit(incident_id, "run_start", status=getattr(inc, "status", "OPEN"))

    # If your Pipeline has a helper, use it; otherwise emit around run_all
    run_all_with_emit = getattr(PIPELINE, "run_all_with_emit", None)
    if callable(run_all_with_emit):
        out = run_all_with_emit(inc, emitter=lambda ev, **d: asyncio.create_task(emit(incident_id, ev, **d)))
    else:
        # coarse-grained emits
        await emit(incident_id, "stage", name="plan")
        await emit(incident_id, "stage", name="remediate")
        await emit(incident_id, "stage", name="validate")
        out = PIPELINE.run_all(inc)

    # Persist (incident mutated by pipeline)
    await repo.upsert(db, inc)
    await db.commit()

    await emit(incident_id, "run_done", status=getattr(inc, "status", "OPEN"))
    return out



class ApproveBody(BaseModel):
    candidate_name: str

@router.post("/{incident_id}/approve", response_model=Incident)
async def approve_candidate(
    incident_id: str,
    candidate_name: Optional[str] = Query(None, description="Name of the remediation candidate"),
    body: Optional[ApproveBody] = None,
    db: AsyncSession = Depends(get_session),
):
    try:
        inc = await repo.get(db, incident_id)
        if not inc:
            raise HTTPException(status_code=404, detail="Incident not found")

        name = candidate_name or (body.candidate_name if body else None)
        if not name:
            raise HTTPException(status_code=422, detail="candidate_name is required")

        target = None
        for c in inc.remediation_candidates:
            if c.name.strip().lower() == name.strip().lower():
                target = c
                break
        if not target:
            raise HTTPException(status_code=404, detail=f"Candidate '{name}' not found")

        target.policy_status = "allowed"
        reasons = list(getattr(target, "policy_reasons", []) or [])
        reasons.append(f"Manually approved via API at {datetime.utcnow().isoformat()}Z")
        target.policy_reasons = reasons

        ctx = AgentContext(incident=inc, settings=PIPELINE.settings)
        PIPELINE.validator.run(ctx)

        await repo.upsert(db, inc)
        await db.commit()
        return inc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Approval error: {e}")


@router.get("/{incident_id}/report.md", response_class=PlainTextResponse)
async def get_report_md(incident_id: str, db: AsyncSession = Depends(get_session)):
    inc = await repo.get(db, incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    ctx = AgentContext(incident=inc, settings=PIPELINE.settings)
    out = PIPELINE.reporter.run(ctx)
    return PlainTextResponse(out.data["report_md"])


@router.get("/{incident_id}/stream")
async def stream_incident(incident_id: str):
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # nginx: disable buffering
    }
    return StreamingResponse(
        sse_stream(incident_id),
        media_type="text/event-stream",
        headers=headers,
    )



@router.get("/{incident_id}/report.html", response_class=HTMLResponse)
async def get_report_html(incident_id: str, db: AsyncSession = Depends(get_session)):
    inc = await repo.get(db, incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    ctx = AgentContext(incident=inc, settings=PIPELINE.settings)
    out = PIPELINE.reporter.run(ctx)
    md = out.data["report_md"]

    try:
        from markdown import markdown as md_to_html  # type: ignore
        html_body = md_to_html(md, extensions=["tables", "fenced_code"])
    except Exception:
        html_body = "<pre>" + _html.escape(md) + "</pre>"

    html_page = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Incident Report — {inc.id}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; padding: 24px; line-height: 1.5; }}
    h1, h2, h3 {{ margin-top: 24px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    code {{ background: #f6f8fa; padding: 2px 4px; border-radius: 4px; }}
    pre {{ background: #f6f8fa; padding: 12px; overflow: auto; }}
    blockquote {{ border-left: 4px solid #ddd; margin: 8px 0; padding: 4px 12px; color: #555; }}
  </style>
</head>
<body>
{html_body}
</body>
</html>"""
    return HTMLResponse(content=html_page)
