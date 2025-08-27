from typing import Dict
from loguru import logger
from ..models.incident import Incident
from ..agents.base import AgentContext
from ..agents.detector import DetectorAgent
from ..agents.investigator import InvestigatorAgent
from ..agents.remediator import RemediatorAgent
from ..agents.validator import ValidatorAgent
from ..agents.reporter import ReporterAgent
from ..adapters.vectorstore import VectorStore
from ..core.config import get_settings

INCIDENTS: Dict[str, Incident] = {}

class Pipeline:
    def __init__(self):
        settings = get_settings()
        self.store = VectorStore(persist_dir=settings.vector_db_dir)
        self._seed_minimal()
        self.detector = DetectorAgent()
        self.investigator = InvestigatorAgent(self.store)
        self.remediator = RemediatorAgent()
        self.validator = ValidatorAgent()
        self.reporter = ReporterAgent()
        self.settings = settings
        # KB sanity
        count = self.store.count()
        if count < settings.kb_min_docs:
            logger.warning("KB has only {} docs (< KB_MIN_DOCS={}). Run seed_kb.py to populate.", count, settings.kb_min_docs)
        else:
            logger.info("KB ready with {} docs.", count)

    def _seed_minimal(self):
        # Two simple docs as a safety net (ok to have duplicates; Chroma dedupes by ID)
        self.store.add("Runbook: Bad Deploy Rollback",
                       "Rollback deploy by reverting last tag; run smoke tests; monitor 5xx & p95.",
                       metadata={"uri": "kb/seed/runbooks/bad-deploy-rollback.md"})
        self.store.add("Runbook: DB Pool Exhaustion",
                       "Increase connection pool by 20%; enable circuit breaker; rate limit hot endpoints.",
                       metadata={"uri": "kb/seed/runbooks/db-pool-exhaustion.md"})

    def run_all(self, incident: Incident):
        ctx = AgentContext(incident=incident, settings=self.settings)
        self.detector.run(ctx)
        INCIDENTS[incident.id] = incident
        self.investigator.run(ctx)
        self.remediator.run(ctx)
        self.validator.run(ctx)
        rep = self.reporter.run(ctx)
        INCIDENTS[incident.id] = incident
        logger.info("Pipeline completed for {}", incident.id)
        return {"incident_id": incident.id, "report_md": rep.data["report_md"]}

PIPELINE = Pipeline()
