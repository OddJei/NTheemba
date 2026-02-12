"""markdown
**Outbox-First Integration — Canonical Guide**

- **Goal**: standardize reliable inter-service communication by making the local Outbox table the primary mechanism for emitting S2S events. Avoid direct synchronous HTTP as the sole delivery path for critical signals (financial, attribution, settlement).

- **Core principles**:
  - Write intent to local `outbox` table within the same DB transaction that mutates application state.
  - Outbox rows include: `event_id`, `producer`, `event_type`, `payload` (JSON), `correlation_id`, `idempotency_key`, `attempts`, `last_error`, `dispatched_at`.
  - OutboxDispatcher runs as a background worker (separate process or thread) that polls undispatched rows and posts to configured sinks with retries and exponential backoff.
  - Persist attempt metadata and do not delete outbox rows on first success; mark `dispatched_at` and optionally archive older dispatched rows via retention job.

- **Delivery semantics**:
  - Exactly-once *attempted* semantics: best-effort delivery with idempotent consumer contracts (use `event_id`/`X-Idempotency-Key`) so consumers can dedupe.
  - Consumers should be idempotent and resilient to reordered events.

- **Auth & headers**:
  - OutboxDispatcher attaches `X-Correlation-Id` and `X-Idempotency-Key` (if set). For authenticated sinks the dispatcher must use a dedicated Outbox internal secret (not a user/service JWT) when posting to internal services; this secret is rotated and stored securely.

- **Operational concerns**:
  - Monitor outbox queue depth and alert on growing undispatched counts.
  - Ensure dispatcher has concurrency controls and per-sink rate-limiting to avoid provider throttling.
  - Provide admin endpoints to requeue/dlq/inspect failed outbox rows.

- **Implementation checklist (per service)**
  - Use `idempotent_execute()` helper when processing external callbacks to avoid double-writing outbox intents.
  - Write outbox rows in the same DB transaction that updates application state to avoid mismatches.
  - Do not perform critical business logic in synchronous remote calls; instead write state and outbox row and rely on dispatcher.

- **When to call upstream synchronously**:
  - Synchronous direct HTTP attempts to other services are prohibited for critical financial or attribution signals. For low-risk UI-only flows a synchronous call may be used but must still write an outbox intent so the dispatcher is the durable delivery path.

- **Consumer contract**:
  - Consumers receiving outbox-delivered HTTP posts must validate `X-Correlation-Id`, idempotency keys, and return 2xx for success. Non-2xx responses cause dispatcher retries.

- **Examples**:
  - `order-delivery` writes `delivery_confirmed` to outbox (authoritative paid attribution). `affiliate-engine` consumes that event via its outbox sink.
  - `payment-revenue` writes `epoch_pool_funding` after reconciliation; `affiliate-engine` consumes it to know authoritative pool amounts.

"""
