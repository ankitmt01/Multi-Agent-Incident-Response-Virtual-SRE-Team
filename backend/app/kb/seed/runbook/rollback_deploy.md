---
title: "Rollback a bad deploy"
service: checkout
severity: high
keywords: [deploy, rollback, 5xx, p95]
---


# Rollback steps
1. Freeze traffic to canary
2. Roll back to last green SHA
3. Clear edge cache
4. Verify KPIs (5xx_rate<0.5%, p95_ms<900)