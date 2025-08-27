# Runbook: Bad Deploy Rollback

- Freeze traffic if supported
- Revert last prod tag
- Redeploy previous good version
- Run smoke tests; monitor 5xx & p95
