# Runbook: External API Degradation

- Add timeout + retries with backoff
- Circuit break after N failures
- Serve cached response if possible
- Notify provider & switch region
