# app/api/routers/incidents.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import PlainTextResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
import html as _html
from datetime import datetime
import uuid
import asyncio, json, time
from sse_starlette.sse import EventSourceResponse

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_session
from app.models.incident import Incident
from app.services.pipeline import PIPELINE

router = APIRouter(prefix="/incidents", tags=["incidents"])

# Repo: class-based preferred, function-based fallback
try:
    from app.repositories.incidents import IncidentRepository
    repo = IncidentRepository()
    _class_repo = True
except Exception:
    from app.repositories import incidents as repo
    _class_repo = False


# ---- List / Get -------------------------------------------------------------
@router.get("", response_model=List[Incident])   # /incidents
@router.get("/", response_model=List[Incident])  # /incidents/
async def list_incidents(db: AsyncSession = Depends(get_session)):
    if _class_repo and hasattr(repo, "list"):
        return await repo.list(db)
    return await repo.get_many(db)  # type: ignore

@router.get("/{incident_id}", response_model=Incident)
async def get_incident(incident_id: str, db: AsyncSession = Depends(get_session)):
    getter = repo.get if (_class_repo and hasattr(repo, "get")) else repo.get_one  # type: ignore
    inc = await getter(db, incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc


# ---- Detect / Run -----------------------------------------------------------
@router.post("/detect", response_model=Incident)
async def detect_incident(incident: Incident, db: AsyncSession = Depends(get_session)):
    if not incident.id:
        incident.id = uuid.uuid4().hex
    if not incident.created_at:
        # DB column is timezone-naive, so use utcnow()
        incident.created_at = datetime.utcnow()

    # Let detector fill severity if missing
    ctx = type("AgentContext", (), {"incident": incident, "settings": PIPELINE.settings})
    PIPELINE.detector.run(ctx)

    # If Severity is an enum instance, store as string to match DB schema
    if getattr(incident, "severity", None) is not None and not isinstance(incident.severity, str):
        incident.severity = getattr(incident.severity, "value", str(incident.severity))

    if _class_repo and hasattr(repo, "upsert"):
        return await repo.upsert(db, incident)
    return await repo.create_or_overwrite(db, incident)  # type: ignore

@router.post("/{incident_id}/run")
async def run_pipeline(incident_id: str, db: AsyncSession = Depends(get_session)):
    getter = repo.get if (_class_repo and hasattr(repo, "get")) else repo.get_one  # type: ignore
    inc = await getter(db, incident_id)
    if not inc:
        raise HTTPException(404, "Incident not found")

    PIPELINE.run_all(inc)

    if _class_repo and hasattr(repo, "upsert"):
        await repo.upsert(db, inc)
    else:
        await repo.create_or_overwrite(db, inc)  # type: ignore

    return {"ok": True}


# ---- Manual approval --------------------------------------------------------
class ApproveBody(BaseModel):
    candidate_name: str

@router.post("/{incident_id}/approve", response_model=Incident)
async def approve_candidate(
    incident_id: str,
    candidate_name: Optional[str] = Query(None),
    body: Optional[ApproveBody] = None,
    db: AsyncSession = Depends(get_session),
):
    getter = repo.get if (_class_repo and hasattr(repo, "get")) else repo.get_one  # type: ignore
    inc = await getter(db, incident_id)
    if not inc:
        raise HTTPException(404, "Incident not found")

    name = candidate_name or (body.candidate_name if body else None)
    if not name:
        raise HTTPException(422, "candidate_name is required")

    target = next((c for c in (inc.remediation_candidates or [])
                   if c.name.strip().lower() == name.strip().lower()), None)
    if not target:
        raise HTTPException(404, f"Candidate '{name}' not found")

    target.policy_status = "allowed"
    reasons = list(getattr(target, "policy_reasons", []) or [])
    reasons.append(f"Manually approved at {datetime.utcnow().isoformat()}Z")
    target.policy_reasons = reasons

    ctx = type("AgentContext", (), {"incident": inc, "settings": PIPELINE.settings})
    PIPELINE.validator.run(ctx)

    if _class_repo and hasattr(repo, "upsert"):
        return await repo.upsert(db, inc)
    return await repo.create_or_overwrite(db, inc)  # type: ignore


# ---- Reports ----------------------------------------------------------------
@router.get("/{incident_id}/report.md", response_class=PlainTextResponse)
async def get_report_md(incident_id: str, db: AsyncSession = Depends(get_session)):
    getter = repo.get if (_class_repo and hasattr(repo, "get")) else repo.get_one  # type: ignore
    inc = await getter(db, incident_id)
    if not inc:
        raise HTTPException(404, "Incident not found")
    ctx = type("AgentContext", (), {"incident": inc, "settings": PIPELINE.settings})
    out = PIPELINE.reporter.run(ctx)
    return PlainTextResponse(out.data["report_md"])

@router.get("/{incident_id}/report.html", response_class=HTMLResponse)
async def get_report_html(incident_id: str, db: AsyncSession = Depends(get_session)):
    getter = repo.get if (_class_repo and hasattr(repo, "get")) else repo.get_one  # type: ignore
    inc = await getter(db, incident_id)
    if not inc:
        raise HTTPException(404, "Incident not found")

    ctx = type("AgentContext", (), {"incident": inc, "settings": PIPELINE.settings})
    out = PIPELINE.reporter.run(ctx)
    md = out.data["report_md"]

    try:
        from markdown import markdown as md_to_html  # type: ignore
        html_body = md_to_html(md, extensions=["tables", "fenced_code"])
    except Exception:
        html_body = "<pre>" + _html.escape(md) + "</pre>"

    html_page = f"""<!doctype html>
<html><head><meta charset="utf-8" />
<title>Incident Report — {inc.id}</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial;padding:24px;line-height:1.5}}
table{{border-collapse:collapse;width:100%;margin:12px 0}}
th,td{{border:1px solid #ddd;padding:8px;text-align:left}}
code{{background:#f6f8fa;padding:2px 4px;border-radius:4px}}
pre{{background:#f6f8fa;padding:12px;overflow:auto}}
blockquote{{border-left:4px solid #ddd;margin:8px 0;padding:4px 12px;color:#555}}
</style></head><body>{html_body}</body></html>"""
    return HTMLResponse(content=html_page)


# ---- Streaming run (SSE) ----------------------------------------------------
@router.get("/{incident_id}/run.stream")
async def run_pipeline_stream(incident_id: str, db: AsyncSession = Depends(get_session)):
    getter = repo.get if (_class_repo and hasattr(repo, "get")) else repo.get_one  # type: ignore
    inc = await getter(db, incident_id)
    if not inc:
        raise HTTPException(404, "Incident not found")

    queue: asyncio.Queue[dict] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def emitter(event: str, **data):
        payload = {"event": event, "ts": time.time(), **data}
        loop.call_soon_threadsafe(queue.put_nowait, payload)

    async def producer():
        try:
            def run_sync():
                PIPELINE.run_all(inc)
            worker = loop.run_in_executor(None, run_sync)

            await queue.put({"event": "run_start", "ts": time.time(), "incident_id": inc.id})

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

            if _class_repo and hasattr(repo, "upsert"):
                await repo.upsert(db, inc)
            else:
                await repo.create_or_overwrite(db, inc)  # type: ignore

            yield {"event": "run_done", "data": json.dumps({"ok": True, "incident_id": inc.id})}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(producer(), ping=15000)
