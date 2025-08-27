from .base import Agent, AgentContext, AgentResult
from ..models.common import AgentName
from ..models.incident import ValidationResult
from loguru import logger

class ValidatorAgent(Agent):
    name = AgentName.validator

    def run(self, ctx: AgentContext) -> AgentResult:
        inc = ctx.incident
        results: list[ValidationResult] = []
        # Placeholder validation: assume first candidate "passes better"
        for i, c in enumerate(inc.remediation_candidates):
            passed = (i == 0)
            results.append(ValidationResult(
                candidate=c.name,
                passed=passed,
                notes="Synthetic validation (replace with sandbox replay + KPIs)",
                kpi_before={"error_rate": 10.0, "latency_p95": 900.0},
                kpi_after={"error_rate": 2.0 if passed else 8.0, "latency_p95": 600.0 if passed else 850.0},
            ))
        inc.validation_results = results
        logger.info("Validator produced {} results", len(results))
        return AgentResult(agent=self.name, ok=True, data=inc, message="Validation completed (synthetic)")
