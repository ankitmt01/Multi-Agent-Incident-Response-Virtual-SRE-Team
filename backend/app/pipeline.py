
from __future__ import annotations
from typing import Any, Dict, List

from .investigators.rag import retrieve_evidence
from .remediator.candidates import generate_candidates
from .validator.validator import validate
from . import store
from .audit import write_event


def _evidence_to_dict(e: Any) -> Dict[str, Any]:
    """Normalize Evidence objects/shims to plain dicts for JSON-friendly storage."""
    # Works for both your Pydantic Evidence and the shim in rag.py
    if hasattr(e, "model_dump"):
        d = e.model_dump()
    elif hasattr(e, "dict"):
        d = e.dict()
    elif isinstance(e, dict):
        d = dict(e)
    else:
        # best-effort getattr
        d = {
            "title": getattr(e, "title", None),
            "score": getattr(e, "score", None),
            "snippet": getattr(e, "snippet", None),
            "uri": getattr(e, "uri", None),
            "source": getattr(e, "source", None),
        }
    # keep only common keys to avoid huge blobs
    return {
        "title": d.get("title"),
        "score": d.get("score"),
        "snippet": d.get("snippet"),
        "uri": d.get("uri") or d.get("source"),
        "service": d.get("service"),
        "kind": d.get("kind"),
    }


def run_all(incident) -> Dict[str, Any]:
    """End-to-end pipeline:
       1) Retrieve RAG evidence
       2) Generate deterministic candidates (policy-checked)
       3) Validate each candidate with CSV replay (before/after windows)
       4) Persist JSON-friendly result in store.RESULTS[incident.id]
    """
    write_event(
        "pipeline_start",
        {"incident_id": incident.id, "service": incident.service, "severity": incident.severity},
    )

    # 1) Evidence (objects -> dicts)
    evidence_objs = retrieve_evidence(incident)
    evidence: List[Dict[str, Any]] = [_evidence_to_dict(e) for e in evidence_objs]
    write_event(
        "pipeline_evidence",
        {
            "incident_id": incident.id,
            "count": len(evidence),
            "top_titles": [e.get("title") for e in evidence[:3]],
        },
    )

    # 2) Actionable plans (already annotated with policy fields)
    candidates = generate_candidates(incident, evidence_objs)
    write_event(
        "pipeline_candidates",
        {
            "incident_id": incident.id,
            "count": len(candidates),
            "ok": sum(1 for c in candidates if c.get("policy_ok")),
            "violating": sum(1 for c in candidates if not c.get("policy_ok")),
        },
    )

    # 3) Validate each plan (offline “what-if”)
    validations: List[Dict[str, Any]] = []
    for c in candidates:
        v = validate(incident, c)  # returns {status, before, after, deltas, notes, candidate_id}
        c["validation"] = v  # attach onto candidate for UI
        validations.append({"plan_id": c.get("id"), "result": v})
        write_event(
            "pipeline_validate",
            {
                "incident_id": incident.id,
                "plan_id": c.get("id"),
                "status": v.get("status"),
                "deltas": v.get("deltas"),
            },
        )

    # 4) Policy summary
    violations_total = sum(len(c.get("policy_violations") or []) for c in candidates)
    policy_summary = "All policies ✅" if violations_total == 0 else f"{violations_total} policy violation(s) across candidates"

    # 5) Persist result
    result: Dict[str, Any] = {
        "incident_id": incident.id,
        "evidence": evidence,
        "candidates": candidates,
        "validations": validations,
        "policy_summary": policy_summary,
    }
    store.RESULTS[incident.id] = result
    write_event("pipeline_end", {"incident_id": incident.id})

    return result


