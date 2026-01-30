# ICE Service — Architecture (Intelligent Central Engine)

## Purpose

The ICE (Intelligent Central Engine) is the authoritative backend that presents canonical data to the bot layer and performs business-critical operations: hydration of cached blobs, reservations and price-locks, payment validation, catalog snapshots, business-rule evaluation (promotions, shipping rules), and audit. ICE exposes synchronous HTTP endpoints for blocking operations and consumes/produces async streams for background hydration and audit.

## Design Goal: Stable Bot Layer Before Backend Exists

ICE is intentionally designed as the **bot-layer-facing contract boundary** (anti-corruption layer).

- The bot layer (Ingress, Bots, Reply, Outbound) must depend only on:
  - ICE bot-facing HTTP endpoints and async streams documented in this file
  - Redis cache blob shapes + metadata (`schema_version`, `hydrated_at`, `stale`)
- The bot layer must NOT call future backend services directly.

This enables building the entire bot layer first and keeping it stable. When the real backend is ready, only ICE's backend-facing adapters change.

### Two-Sided ICE Architecture

1) **Bot-facing layer (stable):**
- Validates requests and enforces schemas
- Produces deterministic, versioned responses
- Owns error codes and idempotency behavior
- Writes/reads the agreed Redis keys/streams

2) **Backend-facing adapters (replaceable):**
- Encapsulate whatever data sources exist today (stub stores, mock datasets, temporary DBs)
- Later switch to real backend microservices/DBs without changing bot-facing contracts

ICE responsibilities:

- Provide authoritative `session`, `order_draft`, `catalog_snapshot`, `product` and `msme_profile` blobs (stored in Postgres JSONB).
- Handle reservations (`reserve_items`) and release operations with TTL and idempotency.
- Apply pricing, taxes, promotions and produce deterministic `price_snapshot`.
- Persist append-only audit of OOB patches and events for replay and traceability.
- Expose hydration endpoints used by Ingress and Node Engines and publish async hydration results to Redis streams when requested.

## Data storage & modeling

- Primary store: Postgres with JSONB columns and indexes for `sessions`, `orders`, `catalog_snapshots`, and `products`.
- Use JSONB schema versions per blob (`schema_version`) and migration tooling for transformations.
- Audit stream: append-only table `oob_audit(events JSONB, created_at)` or a Kafka/Redis stream for high-throughput.
- Provide snapshots for large blobs (catalogs) and reference them by `catalog_snapshot_id` in OOB to avoid copying large data into Redis.

Implementation note (phased delivery): ICE may start with a minimal internal store to satisfy bot-facing contracts. When backend systems arrive, migrate ICE to read/write through backend adapters while keeping the bot-facing shapes stable via `schema_version` and compatibility transforms.

## API Endpoints (recommended)

- POST /api/v1/hydrate/session
  - Body: { event_id, session_id, user_id?, bot_id?, required_blobs: ["session","order_draft","bot_meta"] }
  - Response 200: { hydrated:true, session_blob: {...}, order_draft_blob?: {...}, schema_version }
  - Error: 4xx/5xx with error.code

- POST /api/v1/reserve
  - Body: { event_id, session_id, order_draft: {...}, idempotency_key }
  - Response 200: { reserved:true, reservation_id, reserved_items: [{product_id, qty, price}], ttl_seconds, price_snapshot }
  - On failure: return reason (`OUT_OF_STOCK`, `PRICE_CHANGED`) and suggested corrections

- POST /api/v1/confirm_order
  - Body: { event_id, session_id, reservation_id, payment_info_ref }
  - Response 200: { confirmed:true, order_id, receipt_ref }

- GET /api/v1/catalog/snapshot/{business_id}/{snapshot_id}
  - Returns compact catalog snapshot referenced by `catalog_snapshot_id`.

## Async Streams

- `ice:preload` (req): messages requesting ICE to hydrate blobs asynchronously.
- `ice:hydrated` (resp): ICE writes hydrated blobs or references when ready; consumers subscribe to update Redis cache.
- `oob:audit` (append-only): all applied OOB patches and event metadata.

## Contracts with Bot Layer (Ingress / Node Engine)

- Cache-first pattern: Bot layer reads Redis; on missing or stale blobs it calls ICE `hydrate/session` (sync) or publishes to `ice:preload` (async).
- ICE responses MUST include `schema_version`, `hydrated_at` and source metadata.
- Reservation operations are authoritative and MUST be idempotent — include `event_id` and `idempotency_key`.

## Business Logic & Determinism

- Pricing engine: deterministic application of catalog price + promotions + taxes; produce `price_snapshot_id` and `price_snapshot` blob.
- Reservation engine: allocate inventory and return `reservation_id` with TTL. Implement automatic release after TTL or on explicit cancel.
- Rule engine: central place for business rules (eligibility, delivery zones, merchant-specific flags). Rules evaluation must be deterministic and versioned.

## Error Handling & Idempotency

- Idempotency: every write/operation supports `idempotency_key` and ICE returns previous result when duplicate.
- Transactions: use DB transactions for multi-step operations (reserve + write audit + emit events) and publish events only after commit.
- Retry semantics: clients should retry transient errors (5xx) with backoff; ICE should return clear error codes for permanent failures to avoid retries.

## Security & Access

- Auth: mTLS or JWT between services; scoped service accounts for bots vs external admin.
- Rate-limit: per-client rate limits for expensive operations (reserve, confirm).

## Observability

- Metrics: `ice.hydrate.calls`, `ice.reserve.calls`, `ice.reserve.failures`, `ice.confirm.latency`, `ice.audit.event_count`, `ice.schema.mismatch_count`.
- Tracing: propagate `trace_id` and create spans for `hydrate`, `reserve`, `confirm` and internal DB commits.
- Logs: structured logs with `event_id`, `session_id`, `reservation_id`, `error_code`.

## Performance & Scaling

- Scale read-heavy endpoints horizontally (hydration) with caching layers and Redis writes.
- Ensure `reserve` is strongly consistent — keep these operations on a small set of nodes or use leader-based coordination for inventory writes.

## Sample Requests & Responses

- Hydrate (sync) example

Request:

```json
{
  "event_id": "evt_20251226_100",
  "session_id": "sess_abc123",
  "required_blobs": ["session","order_draft"]
}
```

Response (200):

```json
{
  "hydrated": true,
  "session_blob": {"session_id":"sess_abc123","current_node":"serve_products","schema_version":"1.2","hydrated_at":"2025-12-26T10:00:00Z"},
  "order_draft_blob": {"order_id":"tmp_ord_555","cart":{"items":[],"totals":0.0},"schema_version":"1.1","hydrated_at":"2025-12-26T10:00:00Z"}
}
```

- Reserve example

Request:

```json
{
  "event_id":"evt_20251226_101",
  "session_id":"sess_abc123",
  "order_draft": {"cart":{"items":[{"product_id":"p_123","qty":2}]},"cart_version":5},
  "idempotency_key":"evt_20251226_101"
}
```

Response (200):

```json
{
  "reserved": true,
  "reservation_id": "res_20251226_9001",
  "reserved_items": [{"product_id":"p_123","qty":2,"price":120.0}],
  "ttl_seconds": 900,
  "price_snapshot_id": "ps_20251226_9001"
}
```

- Confirm order example

Request:

```json
{
  "event_id":"evt_20251226_102",
  "session_id":"sess_abc123",
  "reservation_id":"res_20251226_9001",
  "payment_ref":"payref_777"
}
```

Response (200):

```json
{
  "confirmed": true,
  "order_id": "order_20251226_2001",
  "receipt_ref": "rcpt_888",
  "created_at": "2025-12-26T10:05:00Z"
}
```

## Migration & Schema Versioning

- Include `schema_version` on every returned blob. Provide migration tooling and backward compatibility for older bot layers. Support read-time translation where possible.

---

Layered Approach (7 primary)
Bot‑Facing API Layer

HTTP + Redis contracts only.
Endpoints: POST /hydrate/session, POST /reserve, POST /confirm_order.
Owns schemas, error codes, idempotency behavior.
Stable forever.
Transport / API Gateway Layer

FastAPI routing, auth (JWT/mTLS), rate limits.
Input validation, request logging, request IDs.
Application / Domain Layer

Deterministic logic: pricing, reservation, validation rules.
Uses idempotency keys, transactions.
No HTTP or DB knowledge.
Adapter / Integration Layer

Pluggable adapters: MSME, affiliate, payment, inventory, catalog.
Translates external shapes into ICE canonical blobs.
Persistence & Cache Layer

Postgres JSONB for canonical blobs & audit.
Redis for cache + streams (hot data).
Snapshot storage for large catalog blobs.
Async Eventing / Streams Layer

ice:preload, ice:hydrated, oob:audit.
Workers for hydration, cache refresh, TTL cleanup, audit publishing.
Observability & Ops Layer

Metrics, tracing, logs, health checks.
Schema version tooling and migrations.