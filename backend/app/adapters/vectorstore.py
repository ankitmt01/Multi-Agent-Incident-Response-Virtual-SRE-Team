from __future__ import annotations
from typing import List, Tuple, Optional, Dict, Any
from loguru import logger

def _norm_score_from_distance(d: float | None) -> float:
    # Chroma returns a distance (lower is better). Convert to a similarity-like score.
    if d is None:
        return 0.0
    try:
        d = float(d)
    except Exception:
        return 0.0
    return 1.0 / (1.0 + d)  # monotonic in [0, 1] for common distances

class VectorStore:
    """Chroma persistent store if available; fallback to in-memory."""
    def __init__(self, persist_dir: str):
        self.persist_dir = persist_dir
        self._mem: List[Tuple[str, str, Optional[str]]] = []  # (title, text, uri)
        try:
            from chromadb import Client
            from chromadb.config import Settings
            self._chroma = Client(Settings(is_persistent=True, persist_directory=persist_dir))
            self._coll = self._chroma.get_or_create_collection("kb")
            self._use_chroma = True
            logger.info("Chroma vector DB initialized at {}", persist_dir)
        except Exception as e:
            self._use_chroma = False
            self._chroma = None
            self._coll = None
            logger.warning("Chroma unavailable ({}). Using in-memory store.", e)

    def add(self, title: str, text: str, metadata: Optional[Dict[str, Any]] = None, doc_id: Optional[str] = None):
        metadata = metadata or {}
        if self._use_chroma:
            _id = doc_id or f"id_{abs(hash((title, text)))%10_000_000}"
            self._coll.add(documents=[text], metadatas=[{"title": title, **metadata}], ids=[_id])
        else:
            self._mem.append((title, text, metadata.get("uri")))

    def search(self, query: str, k: int = 5, min_score: float = 0.0) -> List[Tuple[str, str, float, Optional[str]]]:
        """
        Returns a list of (title, text, score, uri), sorted by score desc, de-duplicated by uri->title.
        """
        if self._use_chroma:
            # pull extra to allow de-dup then trim
            res = self._coll.query(query_texts=[query], n_results=max(k * 2, k))
            docs = res.get("documents", [[]])[0]
            metas = res.get("metadatas", [[]])[0]
            dists = res.get("distances", [[]])[0]
            raw = []
            for d, m, dist in zip(docs, metas, dists):
                title = (m or {}).get("title", "doc")
                uri = (m or {}).get("uri")
                score = _norm_score_from_distance(dist)
                raw.append((title, d, score, uri))
        else:
            # fallback: naive substring count as score
            counts = []
            ql = query.lower()
            for title, text, uri in self._mem:
                counts.append((title, text, float(text.lower().count(ql)), uri))
            # normalize counts to ~[0,1]
            maxc = max((c for *_rest, c, __ in [(t, x, sc, u) for (t,x,sc,u) in counts]), default=1.0)
            raw = [(t, x, (sc / maxc if maxc > 0 else 0.0), u) for (t, x, sc, u) in counts]

        # filter by score, de-dup (prefer by uri, fallback to title)
        seen_keys = set()
        out: List[Tuple[str, str, float, Optional[str]]] = []
        for t, txt, sc, uri in sorted(raw, key=lambda r: r[2], reverse=True):
            if sc < min_score:
                continue
            key = f"uri::{uri}" if uri else f"title::{t}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            out.append((t, txt, sc, uri))
            if len(out) >= k:
                break
        return out

    def count(self) -> int:
        if self._use_chroma:
            try:
                return self._coll.count()  # type: ignore[attr-defined]
            except Exception:
                return 0
        return len(self._mem)
