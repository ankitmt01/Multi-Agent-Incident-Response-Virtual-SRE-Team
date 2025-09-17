
from __future__ import annotations
import os, glob, sys, traceback, hashlib
from pathlib import Path

PRIMITIVES = (str, int, float, bool)

def _clean_meta(d: dict) -> dict:
    out = {}
    for k, v in (d or {}).items():
        if v is None:
            continue
        out[k] = v if isinstance(v, PRIMITIVES) else str(v)
    return out

def _stable_id_from_path(p: Path) -> str:
    # deterministic across reruns and unaffected by list order
    h = hashlib.sha256(p.as_posix().encode("utf-8")).hexdigest()
    return h

def _title_from_md(p: Path, fallback: str) -> str:
    try:
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = line.strip()
            if s.startswith("#"):
                return s.lstrip("#").strip() or fallback
    except Exception:
        pass
    return fallback

def _infer_kind_service(p: Path, name: str) -> tuple[str, str]:
    parts = [x.lower() for x in p.parts]
    kind = "runbook" if "runbook" in parts else ("incident" if "incidents" in parts or "incident" in parts else "doc")
    stem = p.stem.lower()
    # service from folder or name prefix
    for svc in ["checkout","payments","cart","search","auth","db","cache","api","gateway"]:
        if svc in parts or stem.startswith(svc):
            return kind, svc
    # fallbacks: filename tokens before first '_' or '-'
    token = stem.split("_")[0].split("-")[0]
    return kind, (token if token and token not in {"runbook","incident"} else "generic")

def main():
    VECTOR_DB_DIR = os.getenv("VECTOR_DB_DIR", "/var/lib/chroma")
    # keep default aligned with backend investigator default
    COLLECTION_NAME = os.getenv("COLLECTION_NAME", "knowledge_base_384")
    # recurse into nested dirs by default
    KB_GLOB = os.getenv("KB_GLOB", "backend/app/kb/seed/**/*.md")
    MODEL = os.getenv("CHROMA_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")  # 384 dims

    Path(VECTOR_DB_DIR).mkdir(parents=True, exist_ok=True)

    try:
        import chromadb
        from chromadb.utils import embedding_functions
        print("chromadb version:", getattr(chromadb, "__version__", "unknown"))
    except Exception as e:
        print("ERROR: chromadb import failed:", repr(e))
        raise

    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=MODEL)

    try:
        client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
        coll = client.get_or_create_collection(
            COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
            embedding_function=ef,
        )
    except Exception:
        print("ERROR: creating client/collection:\n", traceback.format_exc())
        raise

    files = sorted(glob.glob(KB_GLOB, recursive=True))
    print(f"KB_GLOB={KB_GLOB} matched {len(files)} files")

    docs, ids, metas = [], [], []
    for fp in files:
        p = Path(fp)
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            text = p.read_text(errors="ignore")
        name = p.name
        title = _title_from_md(p, fallback=name)
        kind, service = _infer_kind_service(p, name)

        meta = _clean_meta({
            "filename": name,
            "path": str(p),
            "uri": f"file://{p.as_posix()}",
            "title": title,
            "kind": kind,
            "service": service,
        })
        docs.append(text)
        ids.append(_stable_id_from_path(p))
        metas.append(meta)

    try:
        if docs:
            if hasattr(coll, "upsert"):
                coll.upsert(documents=docs, metadatas=metas, ids=ids)
            else:
                coll.add(documents=docs, metadatas=metas, ids=ids)
    except Exception:
        print("ERROR: writing to collection failed:\n", traceback.format_exc())
        raise

    try:
        count = coll.count()
    except Exception:
        count = -1
    print(f"Seeded {len(docs)} docs. Collection count now: {count}")

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print("Seeder crashed with error:", repr(e))
        sys.exit(1)
