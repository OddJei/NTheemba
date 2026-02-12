**ICE Service — Focused Mind Map**

- **Responsibility**: Ingress hydration, bot-session orchestration, cart/order reservation & confirmation orchestration, caching (OOB), event emission for downstream automation (affiliate, MSME, audit), and acting as authoritative runtime for bot flows.

- **Outbox-first integration**: ICE MUST write authoritative lifecycle intents (e.g., `ice.hydrated`, `ice.reserved`, `ice.confirmed`, `ice.outbound.persisted`) into a local Outbox table in the same DB transaction that updates state. The OutboxDispatcher is the reliable delivery mechanism to other services. Do NOT rely on Redis streams or synchronous HTTP POSTs for authoritative financial/attribution events.

- **Key endpoints**:
  - `POST /api/v1/hydrate/session` — hydrate session context (idempotent; returns session blob)
  - `POST /api/v1/reserve` — reserve inventory and create order draft (idempotent)
  - `POST /api/v1/confirm` — confirm order (payment initiation, delivery scheduling, affiliate attribution)
  - `POST /api/v1/messages/log` — upsert incoming/outgoing message pairs
  - `GET /health`, `GET /ready`

- **S2S Auth policy**:
  - ICE must accept and forward JWT bearer tokens issued by MSME (claims include `sub`, `role`, `business_id`, optional `affiliate_id`).
  - For ICE → downstream service calls that require attribution (bot-session, payment-revenue, order-delivery, affiliate-engine) ICE MUST forward the MSME-issued `Authorization` header when available.

- **Caching strategy**:
  - Business lookup cache key: `businessdetails:{phone}` — TTL: 24h. Invalidate on `msme.business_updated` outbox events.
  - Catalog snapshot: TTL 5m (cache-first). Product snapshot: TTL 10m. Affiliate session context: TTL 24h (per policy).
  - OOB store: Redis hash `oob:{session_id}` for transient runtime blobs (short TTL, 30–120m depending on object).

- **Idempotency**:
  - All inbound mutation endpoints must honor `X-Idempotency-Key` or `event_id`. Repeated keys must be rejected or return cached deterministic responses — prefer rejecting duplicate critical financial writes (409) but hydrate/reserve may return cached successful result for UX.
  - Persist idempotency records in DB (`IceIdempotencyCache`) for long-lived keys and store a short cache in Redis for quick-hit windows.

- **Hydration behavior**:
  - Two-number flow: If `business_phone` is provided and `business_id` missing, call MSME `GET /business/phone/{phone}` and populate `business_id`.
  - Acquire single-flight lock per `session_id` to avoid concurrent hydrations.
  - Fetch MSME service token via `POST /auth/service-token/{business_id}` and use the token on downstream calls to `bot-session` and other services.
  - Compose session blob from: MSME user & business, bot-session (resolve/create session), catalog/product snapshots, affiliate context (when present), cart/order draft (when present). Persist blob to Postgres and cache in Redis (`cache:session:{session_id}`) 30m.
  - Emit `ice.hydrated` to Outbox (include `session_id`, `business_id`, `correlation_id`, `event_id`).

- **Reservation & Confirmation**:
  - Reservation (`/reserve`) must acquire a Redis lock, validate availability via Cart/Inventory adapters, persist order draft in DB, cache order draft in Redis (60m) and write `ice.reserved` to Outbox in same transaction.
  - Confirmation (`/confirm`) must: acquire lock, check idempotency, create authoritative order, initiate payment via Payment-Revenue (forwarding MSME token), schedule delivery via Order-Delivery, persist confirmed order + delivery task, write `ice.confirmed` to Outbox (include `order_id`, `payment_ref`, `affiliate_context`). Delivery/affiliate failures are logged and emitted to Outbox but do not roll back core confirmation.

- **Event ingestion & invalidation**:
  - ICE subscribes to OutboxDispatcher-delivered events (webhook or push) from MSME and other services for cache invalidation (e.g., `msme.business_updated`) and attribution signals.
  - Do NOT treat Redis stream `stream:ice:hydrated` as authoritative for cross-service flows — persist Outbox rows for guarantees.

- **Adapters & downstream calls**:
  - Use `AdapterFactory` to call: MSME, Bot-Session, Catalog-Inventory, Cart, Payment-Revenue, Order-Delivery, Affiliate-Engine, Notification.
  - Always attach `Authorization: Bearer <msme_token>` when available for attribution-sensitive calls.

- **Concurrency & locks**:
  - Use Redis locks for single-flight operations: hydration (`hydrate:{session_id}`), reserve (`reserve:{session_id}:{cart_id}`), confirm (`confirm:{order_draft_id}`).

- **Observability & audit**:
  - Persist `IceAuditLog` entries for major lifecycle events. Emit Outbox events for audit ingestion.
  - Include `X-Correlation-Id` in all adapter calls and Outbox payloads.

- **Migration notes / refactor tasks**:
  - Replace current Redis stream-based `publish_event` of `ice:hydrated` with Outbox writes and ensure OutboxDispatcher delivers the same payload to the existing Redis stream or webhook sink.
  - Ensure `MsmeEngineAdapter._build_headers()` no longer returns a dummy `Authorization` header for production; prefer fetching and forwarding MSME-issued tokens.
  - Align `businessdetails:{phone}` cache TTL to 24h and invalidate on `msme.business_updated` events.

-- End
**ICE Service — Focused Mind Map**

- **Responsibility**: Central hydration/orchestration service — persists incoming messages, resolves business/customer/session/affiliate, builds OOB, persists canonical blobs to PostgreSQL, and publishes enriched payload to bot lanes.

- **Key endpoints / topics**:
  - Ingest: `ice:ingest` (broker) or `POST /v1/ingest`
  - Bot lane publish: `bot:lane:{bot_type}`
  - Outbound/Session updates: `ice:session:update`, `ice:outbound`
  - Affiliate events: `affiliate:cycle_created`, `affiliate:cycle_attributed`

- **Behavior rules**:
  - Bot resolution: call MSME `/business/phone/{phone}` for `bot_type` and metadata; fallback to `cust`.
  - If no `bot` exists: auto-create `bot` with default `bot_type` (MSME or `cust`).
  - Session resolution: reuse existing `session_id` by `from+platform`; always create a new `cycle` when an affiliate token is present.
  - Emit `affiliate:cycle_created` immediately on cycle creation.
  - Idempotence: `request_id` dedupe (30m window).

- **OOB (Redis)**:
  - Key: `oob:{session_id}` — stores hydrated blobs, cart snapshot, order snapshot, diagnostics.
  - TTL: 24 hours; optimistic CAS updates; up to 3 retries with exponential backoff.

- **Persistence**:
  - Persist canonical hydration blob to PostgreSQL with a TTL column and `ingest_ts`.
  - Transactions: writes to Postgres should be idempotent (use `request_id` and unique constraints).

- **Hydration blob (example)**

```json
{
  "request_id":"abc123",
  "business_blob":{ "business_id":"biz-555", "business_name":"NTheemba" },
  "customer_blob":{ "user_id":"user-222", "phone":"260955000111" },
  "session_blob":{ "session_id":"sess-456","cycle_id":"cycle-999","bot_type":"commerce" },
  "affiliate_blob":null,
  "cart_blob":null,
  "product_snapshot":null
}
```

- **Mermaid flow**:

```mermaid
flowchart TD
  A[Ingress] --> B[ICE Ingest]
  B --> C[Resolve Business (MSME)]
  C --> D[Resolve Session/Cycle]
  D --> E[Build OOB & Persist]
  E --> F[Publish -> bot:lane:{bot_type}]
  E --> G[Emit affiliate events if present]
```

- **Operational notes**:
  - Keep ICE stateless where possible; use Redis and Postgres for state.
  - Expose health endpoints and metrics for queue depth, OOB hits, hydrate latency.
