from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import re, json, math

import chromadb
from chromadb.config import Settings as ChromaSettings
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer, CrossEncoder

from app.core.config import get_settings

@dataclass
class RagHit:
    title: str
    content: str
    score: float
    uri: Optional[str] = None
    meta: Dict[str, Any] = None

def _read_text(path: Path) -> str:
    # md/txt only to keep the footprint small; add PDF later if you like
    return path.read_text(encoding="utf-8", errors="ignore")

_md_h1 = re.compile(r"^#\s+(.+)$", re.MULTILINE)

def _recursive_chunks(text: str, size: int = 800, overlap: int = 120) -> List[str]:
    # simple greedy splitter w/ overlap; you can swap in a fancier splitter later
    words = text.split()
    if not words:
        return []
    chunks, i = [], 0
    while i < len(words):
        chunk = words[i: i + size]
        chunks.append(" ".join(chunk))
        if i + size >= len(words): break
        i += size - overlap
        if i < 0: i = 0
    return chunks

def _first_h1(text: str) -> Optional[str]:
    m = _md_h1.search(text)
    return m.group(1).strip() if m else None

class RAG:
    def __init__(self):
        s = get_settings()
        self._root = Path(s.vector_db_dir).resolve()
        self._collection_name = s.chroma_collection
        self._client = chromadb.PersistentClient(
            path=str(self._root),
            settings=ChromaSettings(allow_reset=False, anonymized_telemetry=False),
        )
        self._coll = self._client.get_or_create_collection(self._collection_name, metadata={"hnsw:space": "cosine"})
        # Embedders
        self._embed = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        self._cross: Optional[CrossEncoder] = None
        try:
            self._cross = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        except Exception:
            self._cross = None  # optional; we’ll fallback gracefully

        # BM25 cache (in-memory tokenized corpus)
        self._bm25_docs: List[List[str]] = []
        self._bm25_map: List[Tuple[str, int]] = []  # (doc_id, idx) -> align to chroma doc

    # ---------- Ingestion ----------
    def ingest_folder(self, folder: str, service: Optional[str] = None, runbook_type: Optional[str] = None,
                      chunk_size: int = 800, overlap: int = 120) -> int:
        p = Path(folder)
        files = [*p.rglob("*.md"), *p.rglob("*.txt")]
        ids, docs, metas = [], [], []
        for f in files:
            raw = _read_text(f)
            title = _first_h1(raw) or f.stem
            for j, ch in enumerate(_recursive_chunks(raw, size=chunk_size, overlap=overlap)):
                doc_id = f"{f.as_posix()}::chunk{j}"
                ids.append(doc_id)
                docs.append(ch)
                metas.append({
                    "path": f.as_posix(),
                    "title": title,
                    "section": ch[:80],
                    "service": service or "",
                    "runbook_type": runbook_type or "",
                })
        if not ids:
            return 0

        # delete existing chunks for these files to avoid dupes
        # (chroma doesn't have per-prefix delete; we’ll rebuild collection if needed)
        self._coll.add(ids=ids, documents=docs, metadatas=metas, embeddings=self._embed.encode(docs, convert_to_numpy=True))
        # refresh BM25 cache
        self._rebuild_bm25()
        return len(ids)

    def _rebuild_bm25(self):
        # pull all docs for BM25 tokenization
        # note: small corpuses only — okay for demo; swap to a lightweight store if needed
        count = self._coll.count()
        if count == 0:
            self._bm25_docs, self._bm25_map = [], []
            return
        # fetch in pages
        self._bm25_docs, self._bm25_map = [], []
        page = 0; page_size = 1000
        while page * page_size < count:
            res = self._coll.get(include=["documents"], limit=page_size, offset=page * page_size)
            for i, doc in enumerate(res["documents"]):
                toks = doc.lower().split()
                self._bm25_docs.append(toks)
                self._bm25_map.append((res["ids"][i], len(self._bm25_docs)-1))
            page += 1
        if self._bm25_docs:
            self._bm25 = BM25Okapi(self._bm25_docs)
        else:
            self._bm25 = None

    # ---------- Search ----------
    def search(self, query: str, top_k: int = 8, fetch_k: int = 24, service: Optional[str] = None) -> List[RagHit]:
        q = query.strip()
        if not q:
            return []

        # Dense
        dense = self._coll.query(
            query_embeddings=self._embed.encode([q], convert_to_numpy=True),
            n_results=min(fetch_k, 100),
            where={"service": service} if service else None,
            include=["documents", "metadatas", "distances", "embeddings"]
        )

        # Keyword (BM25)
        bm_hits: Dict[str, float] = {}
        if hasattr(self, "_bm25") and self._bm25_docs:
            scores = self._bm25.get_scores(q.lower().split())
            # map back to chroma ids
            for (doc_id, idx), s in zip(self._bm25_map, scores):
                if s > 0:
                    bm_hits[doc_id] = float(s)

        # Merge + MMR-ish diversity
        rows = []
        for i in range(len(dense["ids"][0])):
            doc_id = dense["ids"][0][i]
            doc = dense["documents"][0][i]
            meta = dense["metadatas"][0][i] or {}
            # combine normalized scores
            d = dense["distances"][0][i]
            dense_score = 1.0 - float(d)  # cosine -> similarity
            kw_score = bm_hits.get(doc_id, 0.0)
            combo = dense_score + 0.1 * math.log1p(kw_score)
            rows.append((doc_id, doc, meta, combo, dense_score, kw_score))

        # sort by combo
        rows.sort(key=lambda x: x[3], reverse=True)

        # naive MMR: ensure path diversity
        selected, paths = [], set()
        for r in rows:
            path = (r[2].get("path") or "")[:256]
            if path in paths:
                continue
            selected.append(r)
            paths.add(path)
            if len(selected) >= fetch_k:
                break

        # Cross-encoder rerank (optional)
        if self._cross and selected:
            pairs = [(q, r[1]) for r in selected]
            ce_scores = self._cross.predict(pairs)
            for i, s in enumerate(ce_scores):
                # blend a bit with combo to keep density
                selected[i] = (*selected[i][:3], float(0.5 * selected[i][3] + 0.5 * s), *selected[i][4:])
            selected.sort(key=lambda x: x[3], reverse=True)

        # build hits
        hits: List[RagHit] = []
        for r in selected[:top_k]:
            meta = r[2] or {}
            title = meta.get("title") or Path(meta.get("path", "")).stem
            uri = meta.get("path")
            snippet = r[1]
            hits.append(RagHit(title=title, content=snippet, score=float(r[3]), uri=uri, meta=meta))
        return hits

RAG_SVC = RAG()
