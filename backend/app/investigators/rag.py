

# # backend/app/investigators/rag.py
# from __future__ import annotations
# import os
# from typing import Any, Dict, Iterable, List, Optional, Tuple
# import chromadb
# from chromadb.utils import embedding_functions

# # Chroma client
# import chromadb

# # Try importing your models; if not present, fall back to light shims.
# try:
#     from ..models import Incident, Evidence  # type: ignore
#     HAVE_MODELS = True
# except Exception:
#     from pydantic import BaseModel
#     HAVE_MODELS = False

#     class Incident(BaseModel):  # minimal shim
#         id: str
#         service: Optional[str] = None
#         suspected_cause: Optional[str] = None
#         signals: Optional[List[Dict[str, Any]]] = None

#     class Evidence(BaseModel):  # minimal shim
#         title: str
#         score: float
#         snippet: str
#         uri: str
#         source: Optional[str] = None

# VECTOR_DB_DIR = os.getenv("VECTOR_DB_DIR", "/var/lib/chroma")
# COLLECTION_NAME = os.getenv("COLLECTION_NAME", "knowledge_base")
# DEFAULT_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
# MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.30"))  # cosine score (1 - distance)

# def _score_from_distance(distance: Optional[float]) -> float:
#     if distance is None:
#         return 0.0
#     # Chroma returns distance; cosine similarity score = 1 - distance
#     score = 1.0 - float(distance)
#     # Clamp into [0, 1]
#     return max(0.0, min(1.0, score))

# def _build_query(incident: Incident) -> str:
#     # Compose a compact, deterministic query from suspected cause + strongest signals.
#     parts: List[str] = []
#     if getattr(incident, "suspected_cause", None):
#         parts.append(str(incident.suspected_cause))
#     sigs = getattr(incident, "signals", None) or []
#     # Keep top 2 “loud” signals by value if numeric
#     def val(x: Dict[str, Any]) -> float:
#         try:
#             return float(x.get("value", 0))
#         except Exception:
#             return 0.0
#     for s in sorted(sigs, key=val, reverse=True)[:2]:
#         n = s.get("name")
#         v = s.get("value")
#         u = s.get("unit", "")
#         if n is not None and v is not None:
#             parts.append(f"{n}:{v}{u}")
#     if getattr(incident, "service", None):
#         parts.append(f"service:{incident.service}")
#     return " | ".join(parts) or "site reliability incident remediation"

# def _uniq_by_uri(rows: List[Evidence]) -> List[Evidence]:
#     seen: set = set()
#     out: List[Evidence] = []
#     for e in rows:
#         k = getattr(e, "uri", None) or getattr(e, "source", None) or getattr(e, "title", "")
#         if k and k not in seen:
#             seen.add(k)
#             out.append(e)
#     return out

# def retrieve_evidence(
#     incident: Incident,
#     top_k: int = DEFAULT_TOP_K,
#     min_score: float = MIN_SCORE,
#     where: Optional[Dict[str, Any]] = None,
# ) -> List[Evidence]:
#     """
#     Query Chroma with a deterministic prompt built from the incident.
#     Returns Evidence[] with fields: title, score, snippet, uri, source.
#     """
#     client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
#     collection = client.get_or_create_collection(COLLECTION_NAME, metadata={"hnsw:space": "cosine"})

#     query = _build_query(incident)

#     # Optional service filter if present
#     if where is None:
#         where = {}
#     svc = getattr(incident, "service", None)
#     if svc:
#         # Works if you stored metadata like {"service": "..."} during seeding
#         where = {**where, "service": svc}

#     res = collection.query(
#         query_texts=[query],
#         n_results=max(5, top_k * 2),  # over-fetch, then filter
#         where=where or None,
#         include=["documents", "metadatas", "distances"],
#     )

#     docs = (res.get("documents") or [[]])[0]
#     metas = (res.get("metadatas") or [[]])[0]
#     dists = (res.get("distances") or [[]])[0]

#     rows: List[Evidence] = []
#     for doc, meta, dist in zip(docs, metas, dists):
#         score = _score_from_distance(dist)
#         if score < min_score:
#             continue
#         title = (meta or {}).get("title") or (meta or {}).get("filename") or "KB Note"
#         uri = (meta or {}).get("uri") or (meta or {}).get("path") or (meta or {}).get("filename") or ""
#         snippet = (doc or "")[:500]  # keep it short; renderer can trim more

#         if HAVE_MODELS:
#             rows.append(Evidence(title=title, score=score, snippet=snippet, uri=uri, source=uri))
#         else:
#             rows.append(Evidence(title=title, score=score, snippet=snippet, uri=uri, source=uri))  # type: ignore

#     rows = _uniq_by_uri(sorted(rows, key=lambda e: getattr(e, "score", 0.0), reverse=True))
#     return rows[:top_k]


# VECTOR_DB_DIR = os.getenv("VECTOR_DB_DIR", "/var/lib/chroma")
# COLLECTION_NAME = os.getenv("COLLECTION_NAME", "knowledge_base_384")
# EMBED_MODEL = os.getenv("CHROMA_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# def _get_collection():
#     client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
#     ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
#     return client.get_or_create_collection(
#         COLLECTION_NAME,
#         metadata={"hnsw:space": "cosine"},
#         embedding_function=ef,
#     )




# backend/app/investigators/rag.py
from __future__ import annotations
import os
from typing import Any, Dict, List, Optional
import chromadb
from chromadb.utils import embedding_functions

# ---- Config (single source of truth; align with seeder) ----
VECTOR_DB_DIR   = os.getenv("VECTOR_DB_DIR", "/var/lib/chroma")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "knowledge_base_384")
EMBED_MODEL     = os.getenv("CHROMA_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
DEFAULT_TOP_K   = int(os.getenv("RAG_TOP_K", "5"))
MIN_SCORE       = float(os.getenv("RAG_MIN_SCORE", "0.30"))  # cosine similarity (1 - distance)

# ---- Models (graceful shims for import-time failures) ----
try:
    from ..models import Incident, Evidence  # type: ignore
    HAVE_MODELS = True
except Exception:
    from pydantic import BaseModel
    HAVE_MODELS = False
    class Incident(BaseModel):
        id: str
        service: Optional[str] = None
        suspected_cause: Optional[str] = None
        signals: Optional[List[Dict[str, Any]]] = None
    class Evidence(BaseModel):
        title: str
        score: float
        snippet: str
        uri: str
        source: Optional[str] = None

def _score_from_distance(distance: Optional[float]) -> float:
    if distance is None:
        return 0.0
    s = 1.0 - float(distance)
    return max(0.0, min(1.0, s))

def _build_query(incident: Incident) -> str:
    parts: List[str] = []
    if getattr(incident, "suspected_cause", None):
        parts.append(str(incident.suspected_cause))
    sigs = getattr(incident, "signals", None) or []
    def val(x: Dict[str, Any]) -> float:
        try: return float(x.get("value", 0))
        except Exception: return 0.0
    for s in sorted(sigs, key=val, reverse=True)[:2]:
        n = s.get("name"); v = s.get("value"); u = s.get("unit","")
        if n is not None and v is not None:
            parts.append(f"{n}:{v}{u}")
    if getattr(incident, "service", None):
        parts.append(f"service:{incident.service}")
    return " | ".join(parts) or "site reliability incident remediation"

def _uniq_by_uri(rows: List[Evidence]) -> List[Evidence]:
    seen, out = set(), []
    for e in rows:
        k = getattr(e, "uri", None) or getattr(e, "source", None) or getattr(e, "title", "")
        if k and k not in seen:
            seen.add(k); out.append(e)
    return out

def _get_collection():
    client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    return client.get_or_create_collection(
        COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
        embedding_function=ef,
    )

def retrieve_evidence(
    incident: Incident,
    top_k: int = DEFAULT_TOP_K,
    min_score: float = MIN_SCORE,
    where: Optional[Dict[str, Any]] = None,
) -> List[Evidence]:
    coll = _get_collection()
    query = _build_query(incident)

    # Optional service filter
    if where is None:
        where = {}
    svc = getattr(incident, "service", None)
    if svc:
        where = {**where, "service": svc}

    res = coll.query(
        query_texts=[query],
        n_results=max(5, top_k * 2),
        where=where or None,
        include=["documents", "metadatas", "distances"],
    )

    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]

    rows: List[Evidence] = []
    for doc, meta, dist in zip(docs, metas, dists):
        score = _score_from_distance(dist)
        if score < min_score:
            continue
        title = (meta or {}).get("title") or (meta or {}).get("filename") or "KB Note"
        uri = (meta or {}).get("uri") or (meta or {}).get("path") or (meta or {}).get("filename") or ""
        snippet = (doc or "")[:500]
        if HAVE_MODELS:
            rows.append(Evidence(title=title, score=score, snippet=snippet, uri=uri, source=uri))
        else:
            rows.append(Evidence(title=title, score=score, snippet=snippet, uri=uri, source=uri))  # type: ignore

    rows = _uniq_by_uri(sorted(rows, key=lambda e: getattr(e, "score", 0.0), reverse=True))
    return rows[:top_k]
