# Incident Report: INC-BB75C7C1
- Service: payments
- Severity: HIGH
- Status: TRIAGED

## Evidence (Top-k)
- Runbook: Bad Deploy Rollback (score=0.51) [seed/runbooks/bad-deploy-rollback.md]
- Runbook: Bad Deploy Rollback (score=0.50) [kb/seed/runbooks/bad-deploy-rollback.md]
- Runbook: DB Pool Exhaustion (score=0.41) [kb/seed/runbooks/db-pool-exhaustion.md]

## Candidates
- Rollback last deploy
  *status:* **allowed** - Action `deploy.rollback` auto-approved in dev
  *rationale:* 5xx surge coupled with suspected bad deploy â rollback is the fastest blast-radius reducer.
- Toggle off recent feature flag
  *status:* **allowed** - Action `feature.toggle` auto-approved in dev
  *rationale:* If the surge aligns with a feature rollout, toggling off is low-risk + fast.
- Increase DB connection pool & enable circuit breaker
  *status:* **allowed** - Action `db.config_change` auto-approved in dev; Action `traffic.policy` auto-approved in dev; Action `traffic.policy` auto-approved in dev
  *rationale:* Tail latency (1200ms) with 5xx suggests saturation; pool + breaker typically reduces both.

## Validation Results
- Rollback last deploy: PASSED | err 7.622 -> 1.524, p95 1443.3 -> 1010.3
- Toggle off recent feature flag: PASSED | err 7.622 -> 4.573, p95 1443.3 -> 1298.9
- Increase DB connection pool & enable circuit breaker: PASSED | err 7.622 -> 3.049, p95 1443.3 -> 1082.5
