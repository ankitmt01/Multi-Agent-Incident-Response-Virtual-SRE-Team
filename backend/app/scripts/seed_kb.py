from __future__ import annotations
from pathlib import Path
from loguru import logger
from app.core.config import get_settings
from app.adapters.vectorstore import VectorStore
import re

RUNBOOK_TOPICS = [
    ("Bad Deploy Rollback", [
        "Freeze traffic if supported",
        "Revert last prod tag",
        "Redeploy previous good version",
        "Run smoke tests; monitor 5xx & p95"
    ]),
    ("DB Connection Pool Exhaustion", [
        "Increase pool size by 20%",
        "Enable circuit breaker",
        "Add rate-limit for hotspots",
        "Re-run load test"
    ]),
    ("Cache Stampede/Miss Storm", [
        "Introduce request coalescing",
        "Increase TTL for hot keys",
        "Fallback to stale-while-revalidate",
        "Protect origin with rate limits"
    ]),
    ("External API Degradation", [
        "Add timeout + retries with backoff",
        "Circuit break after N failures",
        "Serve cached response if possible",
        "Notify provider & switch region"
    ]),
    ("Hot Partition / Skew", [
        "Enable key sharding",
        "Add rate-limit per key",
        "Warm secondary cache",
        "Scale partitions"
    ]),
]

INCIDENT_TYPES = [
    "Bad deploy → 5xx surge",
    "DB pool exhaustion → latency spikes",
    "Cache miss storm → origin overload",
    "External API timeouts → 502s",
    "Hot partition → uneven load"
]

def ensure_seed_files(seed_root: Path):
    run_dir = seed_root / "runbooks"
    inc_dir = seed_root / "incidents"
    run_dir.mkdir(parents=True, exist_ok=True)
    inc_dir.mkdir(parents=True, exist_ok=True)

    # Create 10 runbooks (repeat topics with slight variations)
    idx = 1
    for title, steps in RUNBOOK_TOPICS:
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        p = run_dir / f"{slug}.md"
        if not p.exists():
            content = "# Runbook: " + title + "\n\n" + "\n".join([f"- {s}" for s in steps]) + "\n"
            p.write_text(content, encoding="utf-8")
        idx += 1
    # Duplicate with slight variations to reach ~10
    for i in range(5):
        p = run_dir / f"bad-deploy-rollback-{i+2}.md"
        if not p.exists():
            p.write_text("# Runbook: Bad Deploy Rollback (Variant)\n\n- Revert last tag\n- Redeploy\n- Smoke tests\n- Monitor 5xx/p95\n", encoding="utf-8")

    # Create ~20 incident notes
    for i in range(20):
        t = INCIDENT_TYPES[i % len(INCIDENT_TYPES)]
        slug = re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")
        p = inc_dir / f"incident-{i+1:03d}-{slug}.md"
        if not p.exists():
            p.write_text(f"# Incident Note: {t}\n\n- Symptoms: ...\n- Impact: ...\n- Fix: ...\n- Postmortem: ...\n", encoding="utf-8")

def iter_markdown(seed_root: Path):
    for p in seed_root.rglob("*.md"):
        text = p.read_text(encoding="utf-8", errors="ignore")
        # Title = first markdown header or filename
        title = None
        for line in text.splitlines():
            if line.strip().startswith("#"):
                title = line.strip("# ").strip()
                break
        if not title:
            title = p.stem.replace("-", " ").title()
        rel = p.relative_to(seed_root.parent)  # start from kb/
        meta = {"uri": f"{rel.as_posix()}"}
        yield title, text, meta

def main():
    settings = get_settings()
    kb_seed_root = Path(__file__).resolve().parents[1] / "kb" / "seed"   # backend/app/kb/seed
    ensure_seed_files(kb_seed_root)

    store = VectorStore(persist_dir=settings.vector_db_dir)
    added = 0
    for title, text, meta in iter_markdown(kb_seed_root):
        store.add(title=title, text=text, metadata=meta)
        added += 1
    logger.info("Seeded {} docs into KB at {}", added, settings.vector_db_dir)
    logger.info("KB doc count now: {}", store.count())

if __name__ == "__main__":
    main()
