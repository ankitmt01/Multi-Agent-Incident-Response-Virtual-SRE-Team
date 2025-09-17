

from __future__ import annotations

import os
import json
import time
import hmac
import httpx
import hashlib
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import anyio
from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    HTMLResponse,
    PlainTextResponse,
    Response,
    StreamingResponse,
)
from prometheus_client import (
    CollectorRegistry, Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
)

# ------------------------------- Optional deps -------------------------------
# Notify (Slack/Jira)
try:
    from .notify import notify_slack, notify_slack_blocks, create_jira_ticket  # type: ignore
except Exception:  # pragma: no cover
    async def notify_slack(*_a, **_k): return None  # type: ignore
    async def notify_slack_blocks(*_a, **_k): return None  # type: ignore
    async def create_jira_ticket(*_a, **_k): return None  # type: ignore

# Audit (best-effort)
try:
    from .audit import AUDIT_FILE, write_event  # type: ignore
except Exception:  # pragma: no cover
    AUDIT_FILE = Path("state/logs/audit.log")  # type: ignore
    def write_event(*_a, **_k): return None  # type: ignore

# Chroma optional
try:
    import chromadb  # type: ignore
except Exception:
    chromadb = None  # type: ignore

# ------------------------------- Local modules -------------------------------
from .config import (
    VECTOR_DB_DIR, KB_MIN_DOCS, ALLOWED_ORIGINS, LOG_LEVEL,
    COLLECTION_NAME, SLACK_SIGNING_SECRET,
)
from .detectors.detector import infer_severity, normalize
from .kb.ingest import add_text_doc, add_url_doc, list_docs, delete_doc, kb_stats
from .logging_setup import configure
from .models import DetectRequest, Incident
from .reporter.html import render_report
from .reporter.pdf import build_pdf
from .reporter.reporter import to_markdown
from .security import require_scopes
from .store import APPROVALS, INCIDENTS, RESULTS, load_state, save_state

# Executor (with safe fallback)
try:
    from .executor import execute_plan  # real engine
except Exception:
    def execute_plan(inc, plan, approved: bool, dry_run: bool = True):
        return {
            "status": "executor_unavailable",
            "incident_id": getattr(inc, "id", None),
            "plan_id": plan.get("id") if isinstance(plan, dict) else None,
            "approved": approved,
            "dry_run": dry_run,
            "message": "Executor import failed",
        }

# --------------------------------- App setup ---------------------------------
log = configure(LOG_LEVEL)
app = FastAPI(title="Incident Copilot MVP v2")

VERSION = {"version": "2.1.0", "build": "local"}
started_at = time.time()

REGISTRY = CollectorRegistry()
INCIDENTS_TOTAL     = Counter("incidents_total", "Incidents created", registry=REGISTRY)
PIPELINE_RUNS_TOTAL = Counter("pipeline_runs_total", "Pipeline runs", registry=REGISTRY)
APPROVALS_TOTAL     = Counter("approvals_total", "Approvals toggled", registry=REGISTRY)
KB_DOCS_GAUGE       = Gauge("kb_docs", "Knowledge base document count", registry=REGISTRY)
EXECUTIONS_TOTAL    = Counter("executions_total", "Plan executions", registry=REGISTRY)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if "*" in ALLOWED_ORIGINS else ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------- Auth deps -----------------------------------
from fastapi import Depends
RUN = Depends(require_scopes(["run"]))
EXEC = Depends(require_scopes(["run"]))      # change to ["execute"] if you want stricter
KB   = Depends(require_scopes(["kb"]))
AUD  = Depends(require_scopes(["audit"]))
ADM  = Depends(require_scopes(["admin"]))

# ---------------------------------- Helpers ----------------------------------
def _try_save_state():
    try:
        save_state()
    except Exception as e:
        log.warning("save_state failed: %s", e)

def kb_count() -> int:
    try:
        if chromadb is None:
            KB_DOCS_GAUGE.set(0)
            return 0
        client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
        col = client.get_or_create_collection(
            name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )
        count = col.count()
        KB_DOCS_GAUGE.set(count)
        return count
    except Exception as e:
        log.warning("KB count failed: %s", e)
        return 0

def _as_dt(x: Any) -> datetime:
    if isinstance(x, datetime): return x
    if isinstance(x, str):
        s = x.strip()
        if s.endswith("Z"): s = s[:-1] + "+00:00"
        try: return datetime.fromisoformat(s)
        except Exception: return datetime.min
    return datetime.min

def _created_at_of(obj: Any) -> datetime:
    if isinstance(obj, dict): return _as_dt(obj.get("created_at"))
    if hasattr(obj, "created_at"): return _as_dt(getattr(obj, "created_at"))
    return datetime.min

def _field_of(obj: Any, name: str) -> Any:
    if isinstance(obj, dict): return obj.get(name)
    return getattr(obj, name, None)

def _to_jsonable(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, dict):
        d = dict(obj)
    elif hasattr(obj, "model_dump"):
        d = obj.model_dump()
    elif hasattr(obj, "dict"):
        d = obj.dict()
    else:
        d = getattr(obj, "__dict__", {})
    ca = d.get("created_at")
    if isinstance(ca, datetime):
        d["created_at"] = ca.isoformat()
    return d

def _as_plain_signal(s: Any) -> Dict[str, Any]:
    if isinstance(s, dict): return s
    if hasattr(s, "model_dump"): return s.model_dump()
    if hasattr(s, "dict"): return s.dict()
    return {
        "name": getattr(s, "name", None),
        "value": getattr(s, "value", None),
        "unit": getattr(s, "unit", None),
        "window_s": getattr(s, "window_s", None),
    }

# -------------------------------- KB endpoints -------------------------------
from pydantic import BaseModel

class KBTextIn(BaseModel):
    title: str
    text: str
    service: Optional[str] = None
    uri: Optional[str] = None
    tags: Optional[List[str]] = None

class KBUrlIn(BaseModel):
    url: str
    title: Optional[str] = None
    service: Optional[str] = None

@app.get("/kb/stats", dependencies=[KB])   # gate stats too; relax if you want it open
def kb_stats_route():
    s = kb_stats()
    KB_DOCS_GAUGE.set(s["count"])
    return s

@app.get("/kb/docs", dependencies=[KB])
def kb_list(limit: int = 50, offset: int = 0):
    return list_docs(limit=limit, offset=offset)

@app.post("/kb/ingest/text", dependencies=[KB])
def kb_ingest_text(payload: KBTextIn):
    out = add_text_doc(
        title=payload.title,
        text=payload.text,
        service=payload.service,
        uri=payload.uri,
        tags=payload.tags,
    )
    KB_DOCS_GAUGE.set(kb_stats()["count"])
    return out

@app.post("/kb/ingest/url", dependencies=[KB])
def kb_ingest_url(payload: KBUrlIn):
    out = add_url_doc(
        url=payload.url,
        title=payload.title,
        service=payload.service,
    )
    KB_DOCS_GAUGE.set(kb_stats()["count"])
    return out

@app.delete("/kb/docs/{doc_id}", dependencies=[KB])
def kb_delete(doc_id: str):
    out = delete_doc(doc_id)
    KB_DOCS_GAUGE.set(kb_stats()["count"])
    return out

# --------------------------------- Lifecycle ---------------------------------
@app.on_event("startup")
def on_startup():
    load_state()
    count = kb_count()
    if count < KB_MIN_DOCS:
        log.warning("[WARN] KB has %s docs (< KB_MIN_DOCS=%s). Seed it.", count, KB_MIN_DOCS)

@app.on_event("shutdown")
def on_shutdown():
    _try_save_state()

# -------------------------------- Basic routes -------------------------------
@app.get("/", response_class=HTMLResponse)
def root():
    p = Path("ui/index.html")
    if p.exists():
        return p.read_text(encoding="utf-8")
    return "<h1>Incident Copilot</h1><p>UI not found.</p>"

@app.get("/health")
def health():
    return {"status": "ok", "kb_docs": kb_count()}

# --------------------------------- Incidents ---------------------------------
@app.post("/incidents/detect", dependencies=[RUN])
def detect(req: DetectRequest):
    try:
        raw_signals = req.signals or []
        if not isinstance(raw_signals, list):
            raise HTTPException(422, "signals must be a list")

        plain_signals = [_as_plain_signal(s) for s in raw_signals]
        signals = normalize(plain_signals)
        severity = infer_severity(signals)
        incident = Incident(service=req.service, severity=severity, suspected_cause=req.suspected_cause)

        INCIDENTS[incident.id] = incident
        write_event("detect", {"incident_id": incident.id, "service": incident.service, "severity": incident.severity})
        INCIDENTS_TOTAL.inc()
        _try_save_state()

        blocks = [
            {"type": "section", "text": {"type": "mrkdwn",
             "text": f"*New incident* `{incident.id}`\nService: *{incident.service}* | Severity: *{incident.severity}*\nSuspected cause: {incident.suspected_cause or '-'}"}},
            {"type": "actions", "block_id": incident.id, "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Approve"}, "style": "primary",
                 "action_id": "approve", "value": incident.id},
                {"type": "button", "text": {"type": "plain_text", "text": "Run pipeline"},
                 "action_id": "run", "value": incident.id},
            ]},
        ]
        try:
            anyio.create_task_group().start_soon(notify_slack_blocks, "Incident created", blocks)
        except Exception:
            pass

        return _to_jsonable(incident)
    except HTTPException:
        raise
    except Exception as e:
        write_event("detect_error", {"error": str(e)})
        raise HTTPException(500, f"detect failed: {e}")

@app.post("/incidents/{incident_id}/execute", dependencies=[EXEC])
def execute_selected_plan(
    incident_id: str,
    plan_id: Optional[str] = None,
    dry_run: bool = True,
):
    inc = INCIDENTS.get(incident_id)
    if not inc:
        raise HTTPException(404, "Incident not found")

    res = RESULTS.get(incident_id)
    if not res:
        raise HTTPException(400, "Run pipeline first: POST /incidents/{id}/run")

    cands = res.get("candidates", [])
    if not cands:
        raise HTTPException(400, "No candidates available to execute")

    pid = plan_id or res.get("chosen_plan_id")
    if not pid:
        policy_ok = [c for c in cands if c.get("policy_ok")]
        pid = (policy_ok[0]["id"] if policy_ok else cands[0]["id"])

    plan = next((c for c in cands if c.get("id") == pid), None)
    if not plan:
        raise HTTPException(404, "Plan not found for this incident")

    approved = bool(APPROVALS.get(incident_id, False))
    exec_result = execute_plan(inc, plan, approved=approved, dry_run=dry_run)

    res.setdefault("executions", []).append(exec_result)
    RESULTS[incident_id] = res
    EXECUTIONS_TOTAL.inc()
    _try_save_state()

    return exec_result

@app.get("/incidents", dependencies=[RUN])
def list_incidents():
    return [_to_jsonable(i) for i in INCIDENTS.values()]

@app.get("/incidents/{incident_id}/candidates", dependencies=[RUN])
def get_candidates(incident_id: str):
    res = RESULTS.get(incident_id)
    if not res:
        raise HTTPException(400, "Run pipeline first: POST /incidents/{id}/run")

    return {
        "candidates": res.get("candidates", []),
        "chosen_plan_id": res.get("chosen_plan_id"),
    }

@app.get("/incidents/{incident_id}/executions", dependencies=[RUN])
def list_executions(incident_id: str):
    res = RESULTS.get(incident_id)
    if not res:
        raise HTTPException(404, "Incident not found or no results")
    return res.get("executions", [])

@app.post("/incidents/{incident_id}/choose", dependencies=[RUN])
def choose_plan(incident_id: str, plan_id: str):
    res = RESULTS.get(incident_id)
    if not res:
        raise HTTPException(400, "Run pipeline first: POST /incidents/{id}/run")
    cands = res.get("candidates", [])
    if not any(c.get("id") == plan_id for c in cands):
        raise HTTPException(404, "Plan not found for this incident")
    res["chosen_plan_id"] = plan_id
    _try_save_state()
    return {"incident_id": incident_id, "chosen_plan_id": plan_id}

@app.post("/incidents/{incident_id}/approve", dependencies=[RUN])
def approve_incident(incident_id: str, approved: bool = True):
    if incident_id not in INCIDENTS:
        raise HTTPException(404, "Incident not found")
    APPROVALS[incident_id] = approved
    write_event("approve", {"incident_id": incident_id, "approved": approved})
    APPROVALS_TOTAL.inc()
    _try_save_state()
    return {"incident_id": incident_id, "approved": approved}

@app.post("/incidents/{incident_id}/run", dependencies=[RUN])
def run_pipeline_endpoint(incident_id: str):
    from .pipeline import run_all
    incident = INCIDENTS.get(incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    result = run_all(incident)
    RESULTS[incident.id] = result
    write_event("run", {"incident_id": incident.id, "approved": bool(APPROVALS.get(incident_id, False))})
    PIPELINE_RUNS_TOTAL.inc()
    _try_save_state()
    return {"message": "Pipeline finished", "incident_id": incident.id, "approved": bool(APPROVALS.get(incident_id, False))}

@app.get("/incidents/{incident_id}/status", dependencies=[RUN])
def incident_status(incident_id: str):
    inc = INCIDENTS.get(incident_id)
    if not inc:
        raise HTTPException(404, "Incident not found")
    has_result = incident_id in RESULTS
    return {
        "incident_id": incident_id,
        "service": inc.service,
        "severity": inc.severity,
        "approved": bool(APPROVALS.get(incident_id, False)),
        "has_result": has_result,
        "report_paths": {
            "markdown": f"/incidents/{incident_id}/report.md" if has_result else None,
            "pdf": f"/incidents/{incident_id}/report.pdf" if has_result else None,
            "html": f"/incidents/{incident_id}/report.html" if has_result else None,
        },
    }

# ---------------------------------- Reports ----------------------------------
@app.get("/incidents/{incident_id}/report.md", dependencies=[RUN], response_class=PlainTextResponse)
def get_report_md(incident_id: str):
    incident = INCIDENTS.get(incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    result = RESULTS.get(incident_id)
    if not result:
        raise HTTPException(400, "Run pipeline first: POST /incidents/{id}/run")
    return to_markdown(incident, result)

@app.get("/incidents/{incident_id}/report.html", dependencies=[RUN], response_class=HTMLResponse)
def get_report_html(incident_id: str, request: Request):
    incident = INCIDENTS.get(incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    result = RESULTS.get(incident_id)
    if not result:
        raise HTTPException(400, "Run pipeline first: POST /incidents/{id}/run")
    return render_report(request, incident, result)

@app.get("/incidents/{incident_id}/report.pdf", dependencies=[RUN])
def get_report_pdf(incident_id: str):
    incident = INCIDENTS.get(incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    result = RESULTS.get(incident_id)
    if not result:
        raise HTTPException(400, "Run pipeline first: POST /incidents/{id}/run")
    pdf = build_pdf(incident, result)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="incident_{incident_id}.pdf"'})

# --------------------------- System / diagnostics ----------------------------
@app.get("/status")
def status():
    return {
        "uptime_seconds": int(time.time() - started_at),
        "kb_docs": kb_count(),
        "incidents_count": len(INCIDENTS),
        "results_count": len(RESULTS),
        "approvals_count": len([k for k, v in APPROVALS.items() if v]),
        "env": {"vector_dir": VECTOR_DB_DIR, "kb_min_docs": KB_MIN_DOCS, "log_level": LOG_LEVEL},
    }

@app.get("/metrics", dependencies=[ADM])
def metrics():
    KB_DOCS_GAUGE.set(kb_count())
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)

@app.get("/audit/tail", dependencies=[AUD])
def audit_tail(n: int = 50):
    try:
        lines = AUDIT_FILE.read_text(encoding="utf-8").splitlines()
        n = max(1, min(n, 1000))
        return lines[-n:]
    except Exception:
        return []

@app.get("/audit/stream", dependencies=[AUD])
async def audit_stream(request: Request):
    """
    SSE stream of audit events.
    """
    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)

    async def _gen():
        with AUDIT_FILE.open("a+", encoding="utf-8") as f:
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if not line:
                    await anyio.sleep(0.5)
                    continue
                yield f"data: {line.rstrip()}\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")

@app.get("/version")
def version():
    return VERSION

@app.get("/liveness")
def liveness():
    return {"status": "alive", "ts": time.time()}

@app.get("/readiness")
def readiness():
    return {"status": "ready", "kb_docs": kb_count(), "uptime": int(time.time() - started_at)}

# ---------------------- Search (robust across types) -------------------------
@app.get("/incidents/search", dependencies=[RUN])
def search_incidents(
    q: str = "",
    service: Optional[str] = None,
    severity: Optional[str] = None,
    sort: str = "-created_at",
    limit: int = 50,
    offset: int = 0,
):
    items: List[Any] = list(INCIDENTS.values())

    ql = q.lower().strip()
    if ql:
        def _match(i: Any) -> bool:
            sid = str(_field_of(i, "id") or "").lower()
            svc = str(_field_of(i, "service") or "").lower()
            cause = str(_field_of(i, "suspected_cause") or "").lower()
            return (ql in sid) or (ql in svc) or (cause.find(ql) >= 0)
        items = [i for i in items if _match(i)]

    if service:
        s = service.lower()
        items = [i for i in items if str(_field_of(i, "service") or "").lower() == s]

    if severity:
        sv = severity.upper()
        items = [i for i in items if str(_field_of(i, "severity") or "").upper() == sv]

    reverse = sort.startswith("-")
    field = sort.lstrip("+-").strip() or "created_at"

    if field == "created_at":
        items.sort(key=_created_at_of, reverse=reverse)
    elif field == "severity":
        order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        items.sort(key=lambda x: order.get(str(_field_of(x, "severity") or "").upper(), 99), reverse=reverse)
    else:
        def _key(o):
            v = _field_of(o, field)
            return (v is None, v)
        items.sort(key=_key, reverse=reverse)

    total = len(items)
    limit = max(0, min(limit, 200))
    page = items[offset: offset + limit]
    return {"total": total, "limit": limit, "offset": offset, "items": [_to_jsonable(x) for x in page]}

# ----------------------------- Demo + Integrations ---------------------------
@app.post("/demo/simulate", dependencies=[RUN])
def demo_simulate():
    req = DetectRequest(
        service="checkout",
        suspected_cause="bad deploy",
        signals=[
            {"name": "5xx_rate", "value": 1.6, "unit": "%", "window_s": 60},
            {"name": "latency_p95_ms", "value": 1200, "unit": "ms", "window_s": 60},
        ],
    )
    return detect(req)

@app.post("/incidents/{incident_id}/jira", dependencies=[RUN])
async def open_jira(
    incident_id: str,
    summary: str | None = Body(default=None),
    description: str | None = Body(default=None),
):
    inc = INCIDENTS.get(incident_id)
    if not inc:
        raise HTTPException(404, "Incident not found")

    if not summary:
        summary = f"[Incident {incident_id}] {inc.service} — {inc.severity}"
    if not description:
        description = (
            f"Auto-created from Incident Copilot.\n"
            f"Service: {inc.service}\n"
            f"Severity: {inc.severity}\n"
            f"Suspected cause: {inc.suspected_cause or '-'}\n"
        )

    issue = await create_jira_ticket(summary, description)
    if not issue:
        raise HTTPException(500, "JIRA not configured or request failed")

    entry = RESULTS.setdefault(incident_id, {})
    entry["jira"] = issue
    _try_save_state()

    try:
        await notify_slack(f"📮 JIRA created for incident {incident_id}: {issue.get('key', '?')}")
    except Exception:
        pass

    return {"incident_id": incident_id, "jira": issue}

# ----------------------------- Slack interactive ----------------------------
def _verify_slack_sig(signing_secret: str, body: bytes, ts: str, sig: str) -> bool:
    try:
        basestring = f"v0:{ts}:{body.decode('utf-8')}"
        digest = hmac.new(signing_secret.encode("utf-8"), basestring.encode("utf-8"), hashlib.sha256).hexdigest()
        if abs(time.time() - int(ts)) > 300:
            return False
        expected = f"v0={digest}"
        return hmac.compare_digest(expected, sig)
    except Exception:
        return False

@app.post("/slack/actions")
async def slack_actions(request: Request):
    raw = await request.body()
    ts = request.headers.get("X-Slack-Request-Timestamp", "")
    sig = request.headers.get("X-Slack-Signature", "")

    if SLACK_SIGNING_SECRET:
        if not _verify_slack_sig(SLACK_SIGNING_SECRET, raw, ts, sig):
            raise HTTPException(401, "Invalid Slack signature")

    form = urllib.parse.parse_qs(raw.decode("utf-8"))
    payload_json = (form.get("payload") or ["{}"])[0]
    payload = json.loads(payload_json)
    actions = payload.get("actions") or []
    if not actions:
        return {"ok": True}

    action = actions[0]
    action_id = action.get("action_id")
    incident_id = action.get("value") or (payload.get("container") or {}).get("block_id")
    response_url = payload.get("response_url")

    if not incident_id or incident_id not in INCIDENTS:
        return {"ok": False, "error": "unknown incident"}

    if action_id == "approve":
        APPROVALS[incident_id] = True
        APPROVALS_TOTAL.inc()
        _try_save_state()
        try:
            if response_url:
                async with httpx.AsyncClient(timeout=5) as c:
                    await c.post(response_url, json={
                        "replace_original": False,
                        "response_type": "ephemeral",
                        "text": f"✅ Approved incident `{incident_id}`."
                    })
        except Exception:
            pass
        return {"ok": True}

    if action_id == "run":
        async def _bg():
            from .pipeline import run_all
            inc = INCIDENTS.get(incident_id)
            if not inc:
                return
            try:
                res = run_all(inc)
                RESULTS[incident_id] = res
                PIPELINE_RUNS_TOTAL.inc()
                _try_save_state()
                try:
                    if response_url:
                        async with httpx.AsyncClient(timeout=5) as c:
                            await c.post(response_url, json={
                                "replace_original": False,
                                "response_type": "ephemeral",
                                "text": f"🏁 Pipeline finished for `{incident_id}`. Report: /incidents/{incident_id}/report.html"
                            })
                except Exception:
                    pass
            except Exception as e:
                try:
                    if response_url:
                        async with httpx.AsyncClient(timeout=5) as c:
                            await c.post(response_url, json={
                                "replace_original": False,
                                "response_type": "ephemeral",
                                "text": f"❌ Pipeline error for `{incident_id}`: {e}"
                            })
                except Exception:
                    pass

        import asyncio
        asyncio.create_task(_bg())
        return {"ok": True, "message": "Pipeline started"}

    return {"ok": False, "error": f"unknown action {action_id}"}

# -------- Latest helpers --------
def _latest_incident_id() -> str:
    if not INCIDENTS:
        raise HTTPException(404, "No incidents")
    def _created(i):
        v = getattr(i, "created_at", None) or (i.dict().get("created_at") if hasattr(i, "dict") else None)
        return _as_dt(v)
    return max(INCIDENTS.values(), key=_created).id

@app.get("/incidents/latest", dependencies=[RUN])
def latest_incident():
    iid = _latest_incident_id()
    inc = INCIDENTS[iid]
    has_result = iid in RESULTS
    return {
        "incident_id": iid,
        "service": inc.service,
        "severity": inc.severity,
        "approved": bool(APPROVALS.get(iid, False)),
        "has_result": has_result,
        "report_paths": {
            "markdown": f"/incidents/{iid}/report.md" if has_result else None,
            "pdf": f"/incidents/{iid}/report.pdf" if has_result else None,
            "html": f"/incidents/{iid}/report.html" if has_result else None,
        },
    }

@app.get("/incidents/latest/report.md", dependencies=[RUN], response_class=PlainTextResponse)
def latest_report_md():
    iid = _latest_incident_id()
    return get_report_md(iid)

@app.get("/incidents/latest/report.html", dependencies=[RUN], response_class=HTMLResponse)
def latest_report_html(request: Request):
    iid = _latest_incident_id()
    return get_report_html(iid, request)

@app.get("/incidents/latest/report.pdf", dependencies=[RUN])
def latest_report_pdf():
    iid = _latest_incident_id()
    return get_report_pdf(iid)
