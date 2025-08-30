from __future__ import annotations
from .base import Agent, AgentContext, AgentResult
from ..models.common import AgentName

def _sev_badge(sev) -> str:
    # Accept Enum or string; render a pretty badge
    name = getattr(sev, "name", None) or str(sev)
    name = str(name).split(".")[-1].upper()
    return {
        "CRITICAL": "🟥 **CRITICAL**",
        "HIGH": "🟧 **HIGH**",
        "MEDIUM": "🟨 **MEDIUM**",
        "LOW": "🟩 **LOW**",
    }.get(name, f"**{name or 'UNKNOWN'}**")

class ReporterAgent(Agent):
    name = AgentName.reporter

    def run(self, ctx: AgentContext) -> AgentResult:
        inc = ctx.incident

        # --- Header / Summary
        lines: list[str] = []
        lines.append(f"# Incident Report — {inc.id}")
        lines.append("")
        lines.append(f"- **Service:** `{inc.service}`")
        lines.append(f"- **Severity:** {_sev_badge(inc.severity)}")
        lines.append(f"- **Status:** `{inc.status}`")
        lines.append(f"- **Created:** {inc.created_at.isoformat()}")
        if inc.suspected_cause:
            lines.append(f"- **Suspected cause:** _{inc.suspected_cause}_")
        lines.append("")

        # --- Signals (table)
        if inc.signals:
            lines.append("## Signals")
            lines.append("")
            lines.append("| source | label | value | unit | window_s | at |")
            lines.append("|---|---:|---:|---|---:|---|")
            for s in inc.signals:
                lines.append(f"| {s.source} | `{s.label}` | {s.value} | {s.unit or ''} | {s.window_s or ''} | {s.at.isoformat()} |")
            lines.append("")

        # --- Evidence
        lines.append("## Evidence (Top-k)")
        if inc.evidence:
            for e in inc.evidence:
                cite = f" ([{e.uri}]({e.uri}))" if e.uri else ""
                lines.append(f"- **{e.title}** — _score {e.score:.2f}_ {cite}")
                if e.content:
                    lines.append(f"  > {e.content.strip()}")
        else:
            lines.append("_No evidence retrieved._")
        lines.append("")

        # --- Candidates
        lines.append("## Remediation Candidates")
        if inc.remediation_candidates:
            for c in inc.remediation_candidates:
                status = c.policy_status or "unknown"
                reasons = (" — " + "; ".join(c.policy_reasons)) if c.policy_reasons else ""
                lines.append(f"### {c.name}")
                lines.append(f"- **Policy:** **{status}**{reasons}")
                if c.rationale:
                    lines.append(f"- **Rationale:** {c.rationale}")
                if c.predicted_impact:
                    lines.append(f"- **Predicted impact:** `{c.predicted_impact}`")
                if c.risks:
                    lines.append(f"- **Risks:** {', '.join(c.risks)}")
                if c.rollback:
                    lines.append(f"- **Rollback:** {', '.join(c.rollback)}")
                if c.actions:
                    actions = [a.get('action_type', '?') for a in c.actions]
                    lines.append(f"- **Actions:** {', '.join(actions)}")
                if c.steps:
                    lines.append("")
                    lines.append("**Steps:**")
                    for i, step in enumerate(c.steps, 1):
                        lines.append(f"  {i}. {step}")
                lines.append("")
        else:
            lines.append("_No candidates proposed._")
        lines.append("")

        # --- Validation
        lines.append("## Validation Results")
        if inc.validation_results:
            lines.append("")
            lines.append("| candidate | result | err before→after | p95 before→after | notes |")
            lines.append("|---|---|---|---|---|")
            for v in inc.validation_results:
                res = "✅ **PASSED**" if v.passed else "❌ **FAILED**"
                err = f"{v.kpi_before.get('error_rate','?')}% → {v.kpi_after.get('error_rate','?')}%"
                p95 = f"{v.kpi_before.get('latency_p95','?')}ms → {v.kpi_after.get('latency_p95','?')}ms"
                lines.append(f"| {v.candidate} | {res} | {err} | {p95} | {v.notes or ''} |")
            lines.append("")
        else:
            lines.append("_No validation results._")

        report_md = "\n".join(lines)
        return AgentResult(agent=self.name, ok=True, data={"report_md": report_md}, message="Report generated")
