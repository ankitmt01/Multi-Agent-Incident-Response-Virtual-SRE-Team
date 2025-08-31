# app/api/routers/incident.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import PlainTextResponse, HTMLResponse
from typing import List, Optional
import html as _html
from datetime import datetime, timezone
import uuid
import asyncio, json, time
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.repositories import incidents as repo
from app.models.incident import Incident
from app.services.pipeline import PIPELINE

router = APIRouter(prefix="/incidents", tags=["incidents"])

# list (support both /incidents and /incidents/)
@router.get("", response_model=List[Incident])
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

    # minimal triage (matches your Detector)
    if not incident.severity:
        from app.models.common import Severity
        incident.severity = Severity.high

    out = await repo.create_or_overwrite(session, incident)
    return out

@router.post("/{incident_id}/run")
async def run_pipeline(incident_id: str, session: AsyncSession = Depends(get_session)):
    inc = await repo.get_one(session, incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    PIPELINE.run_all(inc)              # mutates in-place
    await repo.create_or_overwrite(session, inc)
    return {"ok": True}

# ---------- manual approval ----------
from pydantic import BaseModel
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
    for c in inc.remediation_candidates or []:
        if c.name.strip().lower() == name.strip().lower():
            target = c
            break
    if not target:
        raise HTTPException(status_code=404, detail=f"Candidate '{name}' not found")

    target.policy_status = "allowed"
    reasons = list(getattr(target, "policy_reasons", []) or [])
    reasons.append(f"Manually approved via API at {datetime.utcnow().isoformat()}Z")
    target.policy_reasons = reasons

    # re-run validator so report reflects updated policy immediately
    PIPELINE.validator.run(type("Ctx", (), {"incident": inc, "settings": PIPELINE.settings}))
    out = await repo.create_or_overwrite(session, inc)
    return out

# --- Markdown report
@router.get("/{incident_id}/report.md", response_class=PlainTextResponse)
async def get_report_md(incident_id: str, session: AsyncSession = Depends(get_session)):
    inc = await repo.get_one(session, incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    out = PIPELINE.reporter.run(type("Ctx", (), {"incident": inc, "settings": PIPELINE.settings}))
    return PlainTextResponse(out.data["report_md"])

# --- HTML report
@router.get("/{incident_id}/report.html", response_class=HTMLResponse)
async def get_report_html(incident_id: str, session: AsyncSession = Depends(get_session)):
    inc = await repo.get_one(session, incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    out = PIPELINE.reporter.run(type("Ctx", (), {"incident": inc, "settings": PIPELINE.settings}))
    md = out.data["report_md"]

    try:
        from markdown import markdown as md_to_html  # optional dep
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

# --- SSE stream (no special emitter in pipeline; we stream start/done) ---
@router.get("/{incident_id}/run.stream")
async def run_pipeline_stream(incident_id: str, session: AsyncSession = Depends(get_session)):
    inc = await repo.get_one(session, incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    queue: asyncio.Queue[dict] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    async def producer():
        try:
            await queue.put({"event": "run_start", "ts": time.time(), "incident_id": inc.id})
            def run_sync():
                PIPELINE.run_all(inc)
            worker = loop.run_in_executor(None, run_sync)

            while True:
                if worker.done() and queue.empty():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=0.25)
                except asyncio.TimeoutError:
                    continue
                yield {
                    "event": msg.get("event", "message"),
                    "data": json.dumps({k: v for k, v in msg.items() if k != "event"})
                }

            await repo.create_or_overwrite(session, inc)
            yield {"event": "run_done", "data": json.dumps({"ok": True, "incident_id": inc.id})}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(producer(), ping=15000)

# --- Fire-and-forget async run ---
@router.post("/{incident_id}/run_async")
async def run_pipeline_async(incident_id: str, session: AsyncSession = Depends(get_session)):
    inc = await repo.get_one(session, incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    loop = asyncio.get_running_loop()

    async def run_and_persist():
        def run_sync():
            PIPELINE.run_all(inc)
        await loop.run_in_executor(None, run_sync)
        await repo.create_or_overwrite(session, inc)

    asyncio.create_task(run_and_persist())
    return {"accepted": True, "incident_id": incident_id}
