# Past Incident — Bad Deploy
Symptoms: error_rate > 1.5%, p95 > 1000ms shortly after release.
Mitigation: rollback or disable feature flag, warm caches, re-run smoke tests.
