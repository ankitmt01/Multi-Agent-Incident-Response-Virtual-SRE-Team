from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import PlainTextResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
import html as _html
from datetime import datetime
import uuid

from app.models.incident import Incident
from app.services.pipeline import PIPELINE
from app.services.policy_guard import PolicyGuard
from app.core.db import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories import incidents as repo

router = APIRouter(prefix="/incidents", tags=["incidents"])

@router.get("/", response_model=List[Incident])
async def list_incidents(session: AsyncSession = Depends(get_session)):
    return await repo.get_many(session)

@router.get("/{incident_id}", response_model=Incident)
async def get_incident(incident_id: str, session: AsyncSession = Depends(get_session)):
    inc = await repo.get_one(session, incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc

@router.post("/detect", response_model=Incident)
async def detect_incident(incident: Incident, session: AsyncSession = Depends(get_session)):
    if not incident.signals:
        raise HTTPException(status_code=422, detail="signals must contain at least one item")
    if not incident.id:
        incident.id = uuid.uuid4().hex

    ctx = type("AgentContext", (), {"incident": incident, "settings": PIPELINE.settings})
    PIPELINE.detector.run(ctx)

    # persist header + signals
    out = await repo.create_or_overwrite(session, incident)
    return out

@router.post("/{incident_id}/run")
async def run_pipeline(incident_id: str, session: AsyncSession = Depends(get_session)):
    inc = await repo.get_one(session, incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    PIPELINE.run_all(inc)
    await repo.create_or_overwrite(session, inc)
    return {"ok": True}

# ---------- manual approval ----------
class ApproveBody(BaseModel):
    candidate_name: str

@router.post("/{incident_id}/approve", response_model=Incident)
async def approve_candidate(
    incident_id: str,
    candidate_name: Optional[str] = Query(None, description="Name of the remediation candidate"),
    body: Optional[ApproveBody] = None,
    session: AsyncSession = Depends(get_session),
):
    inc = await repo.get_one(session, incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    name = candidate_name or (body.candidate_name if body else None)
    if not name:
        raise HTTPException(status_code=422, detail="candidate_name is required")

    target = None
    for c in inc.remediation_candidates:
        if c.name.strip().lower() == name.strip().lower():
            target = c; break
    if not target:
        raise HTTPException(status_code=404, detail=f"Candidate '{name}' not found")

    target.policy_status = "allowed"
    reasons = list(getattr(target, "policy_reasons", []) or [])
    reasons.append(f"Manually approved via API at {datetime.utcnow().isoformat()}Z")
    target.policy_reasons = reasons

    # re-run validator so report reflects updated policy immediately
    ctx = type("AgentContext", (), {"incident": inc, "settings": PIPELINE.settings})
    PIPELINE.validator.run(ctx)

    out = await repo.create_or_overwrite(session, inc)
    return out

# --- Markdown report
@router.get("/{incident_id}/report.md", response_class=PlainTextResponse)
async def get_report_md(incident_id: str, session: AsyncSession = Depends(get_session)):
    inc = await repo.get_one(session, incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    ctx = type("AgentContext", (), {"incident": inc, "settings": PIPELINE.settings})
    out = PIPELINE.reporter.run(ctx)
    return PlainTextResponse(out.data["report_md"])

# --- HTML report
@router.get("/{incident_id}/report.html", response_class=HTMLResponse)
async def get_report_html(incident_id: str, session: AsyncSession = Depends(get_session)):
    inc = await repo.get_one(session, incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    ctx = type("AgentContext", (), {"incident": inc, "settings": PIPELINE.settings})
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
