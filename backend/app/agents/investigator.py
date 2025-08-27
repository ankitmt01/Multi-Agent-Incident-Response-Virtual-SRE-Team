from __future__ import annotations
from .base import Agent, AgentContext, AgentResult
from ..models.common import AgentName
from ..models.incident import EvidenceItem
from ..adapters.vectorstore import VectorStore
from ..utils.text import make_snippet
from loguru import logger

KEYWORD_ALIASES = {
    "5xx": ["5xx", "server error", "internal error"],
    "latency_p95": ["latency p95", "p95 latency", "tail latency"],
    "error_rate": ["error rate", "errors %", "failure rate"],
}

def _build_queries(service: str, suspected: str | None, labels: list[str]) -> list[str]:
    q = []
    # 1) suspected cause (if given)
    if suspected and suspected.strip():
        q.append(suspected.strip())

    # 2) service + labels
    if service:
        svc = service.strip()
        if labels:
            q.append(svc + " " + " ".join(set(labels)))
        else:
            q.append(svc)

    # 3) expand common aliases from labels
    alias_terms: list[str] = []
    for l in labels:
        lk = l.lower()
        for key, al in KEYWORD_ALIASES.items():
            if key in lk:
                alias_terms.extend(al)
    if alias_terms:
        q.append(" ".join(sorted(set(alias_terms))))

    # Fall back: at least return service
    if not q:
        q = [service or "incident"]
    # Keep unique order
    seen = set(); out = []
    for s in q:
        if s not in seen:
            seen.add(s); out.append(s)
    return out[:4]  # cap

class InvestigatorAgent(Agent):
    name = AgentName.investigator

    def __init__(self, store: VectorStore):
        self.store = store

    def run(self, ctx: AgentContext) -> AgentResult:
        inc = ctx.incident
        labels = [s.label for s in inc.signals]
        queries = _build_queries(inc.service, inc.suspected_cause, labels)
        logger.info("Investigator queries: {}", queries)

        # Aggregate results across queries, de-dup happens in store.search too
        hits = []
        seen = set()
        for q in queries:
            for (title, text, score, uri) in self.store.search(q, k=4, min_score=0.0):
                key = f"{uri or title}"
                if key in seen:
                    continue
                seen.add(key)
                # create a readable snippet for the report
                terms = [*labels, inc.service, inc.suspected_cause or ""]
                snippet = make_snippet(text, terms, max_len=280)
                hits.append(EvidenceItem(title=title, content=snippet, score=score, uri=uri))

        # sort final evidence by score desc and cap to 3–5
        hits.sort(key=lambda e: e.score, reverse=True)
        inc.evidence = hits[:5]
        msg = f"{len(inc.evidence)} evidence items retrieved"
        logger.info("Investigator: {}", msg)
        return AgentResult(agent=self.name, ok=True, data=inc, message=msg)
