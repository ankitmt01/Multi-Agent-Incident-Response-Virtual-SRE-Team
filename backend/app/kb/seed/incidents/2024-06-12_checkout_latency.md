---
service: checkout
summary: "Latency regression after DB connection pool misconfig"
keywords: [db_pool, latency, p95]
---


Observed p95=1200ms, 5xx_rate=0.8%. Root cause was pool max too low; fix increased max pool and warmed connections.