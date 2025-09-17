# Past Incident — External API Latency
Symptoms: p95 spike aligned with upstream provider errors.
Mitigation: increase timeout + retries, add circuit breaker, cache last-good response.
