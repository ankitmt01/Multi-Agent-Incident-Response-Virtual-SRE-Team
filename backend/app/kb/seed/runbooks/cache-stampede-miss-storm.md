# Runbook: Cache Stampede/Miss Storm

- Introduce request coalescing
- Increase TTL for hot keys
- Fallback to stale-while-revalidate
- Protect origin with rate limits
