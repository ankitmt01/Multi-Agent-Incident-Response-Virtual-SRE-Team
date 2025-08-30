from typing import List, Tuple
from loguru import logger

class VectorStore:
    """Thin wrapper. Uses Chroma if available; otherwise stores docs in-memory."""
    def __init__(self, persist_dir: str):
        self.persist_dir = persist_dir
        self._mem: List[Tuple[str, str]] = []
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
            logger.warning("Chroma unavailable ({}). Falling back to in-memory store.", e)

    def add(self, title: str, text: str):
        if self._use_chroma:
            self._coll.add(documents=[text], metadatas=[{"title": title}], ids=[f"id_{len(text)}_{len(title)}"])
        else:
            self._mem.append((title, text))

    def search(self, query: str, k: int = 3) -> List[Tuple[str, str, float]]:
        if self._use_chroma:
            res = self._coll.query(query_texts=[query], n_results=k)
            docs = res.get("documents", [[]])[0]
            metas = res.get("metadatas", [[]])[0]
            dists = res.get("distances", [[]])[0]
            out = []
            for d, m, s in zip(docs, metas, dists):
                out.append((m.get("title", "doc"), d, float(s if s is not None else 0.0)))
            return out
        # Fallback: naive substring score
        scored = []
        for title, text in self._mem:
            score = text.lower().count(query.lower())
            scored.append((title, text, float(score)))
        return sorted(scored, key=lambda x: x[2], reverse=True)[:k]
