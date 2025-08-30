from __future__ import annotations
from fastapi import APIRouter, BackgroundTasks, Query
from pydantic import BaseModel
from typing import List, Optional
from app.services.rag import RAG_SVC, RagHit
from app.core.config import get_settings

router = APIRouter(prefix="/kb", tags=["kb"])

class IngestBody(BaseModel):
    folder: Optional[str] = None
    service: Optional[str] = None
    runbook_type: Optional[str] = None

@router.post("/reindex")
def reindex(body: IngestBody, bg: BackgroundTasks):
    s = get_settings()
    folder = body.folder or "./kb/dropbox"
    def _run():
        RAG_SVC.ingest_folder(folder, service=body.service, runbook_type=body.runbook_type)
    bg.add_task(_run)
    return {"ok": True, "message": f"Reindex started for {folder}"}

@router.get("/search")
def search(q: str = Query(..., min_length=2), top_k: int = 8, fetch_k: int = 24, service: Optional[str] = None):
    hits = RAG_SVC.search(q, top_k=top_k, fetch_k=fetch_k, service=service)
    return [{"title": h.title, "content": h.content, "score": h.score, "uri": h.uri, "meta": h.meta} for h in hits]
