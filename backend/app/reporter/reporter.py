# backend/app/reporter/reporter.py
from __future__ import annotations
from typing import Any, Dict, List, Optional
from datetime import datetime


def _as_iso(x: Any) -> Optional[str]:
    if isinstance(x, datetime):
        return x.isoformat()
    if isinstance(x, str):
        return x
    return None


def _fmt_float(x: Any, nd: int = 3) -> str:
    try:
        return f"{float(x):.{nd}f}"
    except Exception:
        return "-"


def _fmt_step(step: Dict[str, Any]) -> str:
    """Render a remediation step as a compact bullet."""
    parts: List[str] = []
    a = (step.get("action_type") or "read").lower()
    svc = step.get("service") or "-"
    env = step.get("env") or "-"
    parts.append(f"*{a}* @{env}/{svc}")
    # include common fields if present
    for k in ("cmd", "key", "value", "op", "version", "backup_id"):
        if step.get(k) not in (None, "", []):
            parts.append(f"{k}={step[k]}")
    targets = step.get("targets")
    if targets:
        parts.append(f"targets={targets}")
    return " — " + ", ".join(parts)


def _render_evidence(ev_list: List[Dict[str, Any]]) -> List[str]:
    lines: List[str] = ["## Evidence", ""]
    if not ev_list:
        lines.append("- No evidence found.")
        return lines
    for ev in ev_list:
        title = ev.get("title") or "KB Document"
        uri = ev.get("uri") or ""
        score = ev.get("score")
        score_s = f" (score: {_fmt_float(score, 3)})" if score is not None else ""
        lines.append(f"- **{title}**{score_s} — {uri}")
    return lines


def _render_candidates(cands: List[Dict[str, Any]]) -> List[str]:
    lines: List[str] = ["## Candidates", ""]
    if not cands:
        lines.append("- No candidates generated.")
        return lines

    for c in cands:
        title = c.get("title") or c.get("id") or "Plan"
        env = c.get("env") or "-"
        svc = c.get("service") or "-"
        ok = bool(c.get("policy_ok"))
        pred = c.get("predicted_impact") or {}
        ri = c.get("rationale") or ""
        status = "OK ✅" if ok else "BLOCKED ⛔"
        lines.append(f"### {title}")
        lines.append(f"- Env/Service: `{env}` / `{svc}`")
        lines.append(f"- Policy: **{status}**")
        if pred:
            lines.append(f"- Predicted impact: error_rate_pct {pred.get('error_rate_pct')}, latency_p95_ms {pred.get('latency_p95_ms')}")
        if ri:
            lines.append(f"- Rationale: {ri}")

        steps = c.get("steps") or []
        if steps:
            lines.append("- Steps:")
            for s in steps:
                lines.append(f"  - {_fmt_step(s)}")

        # Inline per-candidate validation (if present)
        v = c.get("validation")
        if v:
            lines.append("- Validation:")
            lines.append(f"  - Status: **{v.get('status','UNKNOWN')}**")
            b = v.get("before") or {}
            a = v.get("after") or {}
            d = v.get("deltas") or {}
            lines.append(
                f"  - Before → After: "
                f"err% {_fmt_float(b.get('error_rate_pct'))} → {_fmt_float(a.get('error_rate_pct'))}, "
                f"p95 {_fmt_float(b.get('latency_p95_ms'))}ms → {_fmt_float(a.get('latency_p95_ms'))}ms"
            )
            lines.append(
                f"  - Δ (relative): err {_fmt_float(d.get('error_rate_drop_rel'))}, p95 {_fmt_float(d.get('latency_p95_drop_rel'))}"
            )
            if v.get("notes"):
                lines.append(f"  - _{v['notes']}_")

        # Policy violations details
        viols = c.get("policy_violations") or []
        if viols:
            lines.append("- Policy violations:")
            for v in viols:
                lines.append(f"  - [{v.get('code')}] {v.get('message')}")
        lines.append("")  # spacing
    return lines


def _render_policy_summary(result: Dict[str, Any]) -> List[str]:
    lines: List[str] = ["## Policy", ""]
    lines.append(f"- Summary: {result.get('policy_summary', '-')}")
    return lines


def _render_validations_summary(result: Dict[str, Any]) -> List[str]:
    lines: List[str] = ["## Validation (Summary)", ""]
    vals = result.get("validations") or []
    if not vals:
        lines.append("- No validation runs.")
        return lines
    for v in vals:
        rid = v.get("plan_id") or "-"
        rr = v.get("result") or {}
        lines.append(f"- Plan `{rid}` → **{rr.get('status','UNKNOWN')}** "
                     f"(errΔ={_fmt_float((rr.get('deltas') or {}).get('error_rate_drop_rel'))}, "
                     f"p95Δ={_fmt_float((rr.get('deltas') or {}).get('latency_p95_drop_rel'))})")
    return lines


def to_markdown(incident, result: Dict[str, Any]) -> str:
    """Render a complete, human-readable incident report in Markdown."""
    lines: List[str] = []

    # Header
    inc_id = getattr(incident, "id", None) or (incident.get("id") if isinstance(incident, dict) else "")
    service = getattr(incident, "service", None) or (incident.get("service") if isinstance(incident, dict) else "")
    severity = getattr(incident, "severity", None) or (incident.get("severity") if isinstance(incident, dict) else "")
    cause = getattr(incident, "suspected_cause", None) or (incident.get("suspected_cause") if isinstance(incident, dict) else "")
    created = getattr(incident, "created_at", None) or (incident.get("created_at") if isinstance(incident, dict) else None)

    lines.append(f"# Incident Report — {inc_id}")
    lines.append("")
    lines.append(f"- **Service:** `{service}`")
    lines.append(f"- **Severity:** `{severity}`")
    lines.append(f"- **Suspected cause:** {cause or '-'}")
    iso = _as_iso(created)
    if iso:
        lines.append(f"- **Created at:** {iso}")
    lines.append("")

    # Evidence
    lines += _render_evidence(result.get("evidence") or [])
    lines.append("")

    # Candidates (with inline validation + violations)
    lines += _render_candidates(result.get("candidates") or [])
    lines.append("")

    # Policy summary
    lines += _render_policy_summary(result)
    lines.append("")

    # Validation summary table
    lines += _render_validations_summary(result)
    lines.append("")

    # Optional: ticketing info (if present in result)
    jira = result.get("jira")
    if jira:
        lines.append("## Ticket")
        key = jira.get("key") or "-"
        url = jira.get("self") or ""
        lines.append(f"- JIRA: **{key}** — {url}")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("_Generated by Incident Copilot_")

    return "\n".join(lines)
