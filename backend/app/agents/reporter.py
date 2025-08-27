from .base import Agent, AgentContext, AgentResult
from ..models.common import AgentName

class ReporterAgent(Agent):
    name = AgentName.reporter

    def run(self, ctx: AgentContext) -> AgentResult:
        inc = ctx.incident
        lines = [
            f"# Incident Report: {inc.id}",
            f"- Service: {inc.service}",
            f"- Severity: {inc.severity}",
            f"- Status: {inc.status}",
            "",
            "## Evidence (Top-k)",
        ]
        for e in inc.evidence:
            cite = f" [{e.uri}]" if e.uri else ""
            lines.append(f"- {e.title} (score={e.score:.2f}){cite}")
        lines.append("\n## Candidates")
        for c in inc.remediation_candidates:
            lines.append(f"- {c.name}: {c.rationale}")
        lines.append("\n## Validation Results")
        for v in inc.validation_results:
            lines.append(f"- {v.candidate}: {'PASSED' if v.passed else 'FAILED'} | "
                         f"err {v.kpi_before['error_rate']}→{v.kpi_after['error_rate']}, "
                         f"p95 {v.kpi_before['latency_p95']}→{v.kpi_after['latency_p95']}")
        report_md = "\n".join(lines)
        return AgentResult(agent=self.name, ok=True, data={"report_md": report_md}, message="Report generated")
