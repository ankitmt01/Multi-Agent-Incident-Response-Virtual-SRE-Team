# Runbook — Rollback Procedure
If a deployment causes elevated 5xx and p95 spikes, initiate rollback to previous stable version.
Steps:
1. Identify latest deployment ID.
2. Execute rollback.
3. Warm caches and verify metrics.
