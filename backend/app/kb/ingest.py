# backend/app/kb/ingest.py
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import hashlib
import requests

# Reuse the exact same collection + embedding function as RAG
from ..investigators.rag import _get_collection

def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

def _mk_id(title: str, text: str, service: Optional[str] = None) -> str:
    base = f"{title}::{service or ''}::{text[:256]}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()

def add_text_doc(
    title: str,
    text: str,
    *,
    service: Optional[str] = None,
    uri: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    col = _get_collection()
    doc_id = _mk_id(title, text, service)
    meta = {
        "title": title,
        "service": service,
        "uri": uri,
        "tags": tags or [],
        "created_at": _now_iso(),
        "kind": "kb_manual",
    }
    col.upsert(ids=[doc_id], documents=[text], metadatas=[meta])
    return {"id": doc_id, "title": title, "service": service, "uri": uri}

def add_url_doc(
    url: str,
    *,
    title: Optional[str] = None,
    service: Optional[str] = None,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    content = resp.text
    t = title or url
    return add_text_doc(t, content, service=service, uri=url, tags=["url"])

def list_docs(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    col = _get_collection()
    # fetch a window of docs (Chroma returns in arbitrary order)
    res = col.get(include=["metadatas", "documents"], limit=limit, offset=offset)
    items = []
    for i, meta in enumerate(res.get("metadatas", [])):
        items.append({
            "id": res["ids"][i],
            "title": (meta or {}).get("title"),
            "service": (meta or {}).get("service"),
            "uri": (meta or {}).get("uri"),
            "tags": (meta or {}).get("tags"),
            "created_at": (meta or {}).get("created_at"),
            "kind": (meta or {}).get("kind", "kb"),
            "snippet": (res.get("documents") or [""])[i][:400],
        })
    return {
        "total": col.count(),
        "limit": limit,
        "offset": offset,
        "items": items,
    }

def delete_doc(doc_id: str) -> Dict[str, Any]:
    col = _get_collection()
    col.delete(ids=[doc_id])
    return {"deleted": [doc_id]}

def kb_stats() -> Dict[str, Any]:
    col = _get_collection()
    return {"count": col.count()}
