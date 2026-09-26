# Phase 12.1 — Redis Foundation

Phase 12.1 adds an asynchronous Redis runtime, explicit lifecycle management, namespaced keys and readiness checks.

Keys use this structure:

```text
{prefix}:{environment}:{resource}:{encoded tenant segments}
```

Business IDs, customer IDs and external idempotency values are base64url encoded before they enter Redis keys. This prevents delimiter collisions and keeps environment/tenant boundaries explicit.

The Redis dependency is imported only when `NTHEEMBA_SESSION_BACKEND=redis`. Memory-only tests therefore do not require a running Redis service.
