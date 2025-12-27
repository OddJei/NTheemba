# Bot Ingress Service — Architecture

## Purpose

The Bot Ingress Service accepts inbound messages from external channels (SMS, WhatsApp, HTTP callbacks), validates and normalizes them, enriches payloads (cache-first) with bot, user and session data, and routes the enriched envelope into the internal pipeline. Ingress is responsible for idempotency checks, short-term caching for hot-path decisions, preload triggers for ICE hydration, and publishing to the appropriate Redis streams/lanes. Ingress aims to keep routing decisions fast and deterministic so downstream bot workers (Intent, Reply, Outbound) only run when required.

## Inputs

- External channels: SMS / WhatsApp / HTTP callbacks (provider-specific inbound payloads)
- Stream: `ingress:incoming` — normalized raw inbound JSON

Ingress must validate required fields and enrich the envelope with `session_id` and `enrichment.meta` before publishing.

## Outputs

- Stream: `bot:lane:{bot_type}` (primary publish target) — canonical, enriched envelope for low-latency bot processing (e.g., `bot:lane:custom`, `bot:lane:default`).
- Stream: `ingress:resolved_payload` (audit/observability) — canonical resolved envelope for replay, auditing and analytics.
- Stream: `ingress:dlq` — dead-letter queue for unprocessable events after retry.
- ICE: `ice:preload` (async) and `POST /api/v1/hydrate/session` (sync) — authoritative hydration when cache misses or fields are stale.
- Telemetry/logging/traces to observability backend.

## Queue Contracts

Streams and envelope contract (minimal):

- Stream: `ingress:incoming`
  - Message: raw inbound JSON (see Inputs)

- Stream: `ingress:resolved_payload`
  - Message structure (envelope):
    - `event_id` (string)
    - `session_id` (string)
    - `user_id` (string | null)
    - `bot_id` (string | null)
    - `bot_type` (string | eg. `custom|default`)
    - `enriched` (object): metadata plus resolved blobs (session_context, user, bot_meta references)
    - `routing_hints` (object): `{ "bot_lane": "bot:lane:custom", "intent_required": true|false, "route_version": "v1" }`
    - `raw` (original message payload)

- Stream: `ingress:dlq`
  - Contains failed envelope and `error` + `attempts` metadata.

Publishing rules:

- Default: publish directly to `bot:lane:{bot_type}` with the canonical enriched envelope.
- Canonical write: always persist the same canonical enriched envelope to `ingress:resolved_payload` for replay/audit (sync or via a reliable async replicator).
- Fallback: if `bot:lane:{bot_type}` publish fails irrecoverably, push the envelope to `ingress:dlq` after retries. The `ingress:resolved_payload` record must reflect the failure state.

## Cache/State (Redis)

Ingress uses a cache-first approach for hot-path routing/enrichment and calls ICE when required blobs are missing or stale.

### Redis Key Reference (Ingress)

Below is the canonical key list Ingress will use. Ingress must ensure these blobs are preloaded (cache-first) and call ICE when missing or missing authoritative fields.

| Key pattern | TTL (recommend) | Purpose | Minimal fields |
|---|---:|---|---|
| `cache:session:{session_id}` | session timeout (e.g. 1800s) | Fast session lookup for routing & node decisions | `session_id`, `user_id`, `bot_id`, `bot_type`, `session_mode`, `current_node`, `expected_input`, `intent_required`, `order_draft_key`, `last_active_at`, `schema_version`, `hydrated_at` |
| `cache:order_draft:{session_id}` | session timeout | Mutable order draft used by bot for cart/checkout flow | `order_id`, `items[] {product_id,name,qty,price_snapshot}`, `fulfillment{type,location,fee,status}`, `payment{method,status,tx_id}`, `status`, `updated_at`, `schema_version` |
| `cache:bot_meta:{bot_id}` or `cache:bot_meta:{bot_phone}` | 3600s | Bot / MSME config used for routing and menus | `bot_id`, `business_id`, `business_name`, `default_locale`, `delivery_areas_ref`, `supported_payment_methods`, `contact`, `config_flags`, `schema_version` |
| `cache:user:{user_id}` or `cache:user:{phone}` | 900–3600s | Resolved user profile for personalization & routing | `user_id`, `phone_masked`, `name`, `roles`, `is_authenticated`, `linked_business_id`, `preferences`, `last_seen`, `schema_version` |
| `cache:capabilities:{mode}` | 3600s | Allowed actions + UI hints per session mode | `mode`, `allowed_actions[]`, `ui_hints`, `schema_version` |
| `cache:catalog_snapshot:{business_id}:{snapshot_id}` | 300–900s | Pre-rendered product list for menus (separate snapshot avoids copying) | `snapshot_id`, `generated_at`, `products[] {product_id,name,price_snapshot,availability_flag,short_desc}`, `schema_version` |
| `cache:product:{product_id}` | 300s | Quick product detail lookup used for details views | `product_id`, `name`, `price_snapshot`, `stock_status`, `msme_id`, `schema_version` |
| `cache:msme_profile:{business_id}` | 3600s | MSME profile for pickup/delivery logic | `business_id`, `name`, `pickup_locations[]`, `delivery_areas[]`, `contact`, `schema_version` |
| `idempotency:request:{request_id}` | depends on retry window (e.g. 86400s) | Prevent duplicate inbound processing | value: processing marker / resulting `event_id` |
| `preload:pending:{session_id}` | short (e.g. 60s) | Trigger flag to avoid duplicate hydrations when Ingress kicks off preload | minimal boolean marker, `requested_at`, `requested_by_event` |

### Blob metadata (required in every cached JSON)

- `schema_version` — semantic version of blob layout
- `hydrated_at` — UTC timestamp of last ICE hydration
- `last_hydrated_by:event_id` — event id that triggered hydration
- `stale` (optional bool) — set true when ICE hydration failed and cache used anyway

### Example JSON samples

- `cache:session:{session_id}` sample

```json
{
 "session_id": "sess_abc123",
 "user_id": "user_789",
 "bot_id": "bot_456",
 "bot_type": "custom",
 "session_mode": "customer",
 "current_node": "inspect_cart_item",
 "expected_input": "confirmation",
 "intent_required": false,
 "order_draft_key": "cache:order_draft:sess_abc123",
 "last_active_at": "2025-12-25T12:34:56Z",
 "schema_version": "1.0",
 "hydrated_at": "2025-12-25T12:30:00Z"
}
```

- `cache:order_draft:{session_id}` sample

```json
{
 "order_id": "tmp_ord_987",
 "items": [
  {"product_id": "p_123", "name": "Solar Panel A", "quantity": 2, "price_snapshot": 120.0}
 ],
 "fulfillment": {"type": "delivery", "location": "Kitwe Depot", "fee": 50, "status": "pending"},
 "payment": {"method": null, "status": "pending", "tx_id": null},
 "status": "building",
 "updated_at": "2025-12-25T12:34:56Z",
 "schema_version": "1.0"
}
```

- `cache:bot_meta:{bot_id}` sample

```json
{
 "bot_id": "bot_456",
 "business_id": "biz_321",
 "business_name": "Kitwe Solar",
 "default_locale": "en",
 "delivery_areas_ref": "cache:msme_profile:biz_321",
 "supported_payment_methods": ["mobile_money", "cash"],
 "config_flags": {"allow_pickup": true},
 "schema_version": "1.0"
}
```

- `cache:catalog_snapshot:{business_id}:{snapshot_id}` sample

```json
{
 "snapshot_id": "snap_20251225_001",
 "generated_at": "2025-12-25T12:00:00Z",
 "products": [
  {"product_id": "p_123", "name": "Solar Panel A", "price_snapshot": 120.0, "availability_flag": "in_stock", "short_desc": "100W panel"}
 ],
 "schema_version": "1.0"
}
```

These keys and blob shapes keep Redis small and focused on hot-path reads while ICE (Postgres JSONB) remains the authoritative store for full objects and history. Ingress must ensure preload triggers and hydration rules are followed so the bot finds necessary data in Redis in time; when critical fields are missing the bot must call ICE for authoritative validation.

### Cart / Order Draft Management (Ingress guidance)

Ingress responsibilities for cart/order_draft handling:
- Ensure `cache:order_draft:{session_id}` is populated on session start or when cart-affecting events arrive. Use `preload:pending:{session_id}` to dedupe hydrations.
- Write-through vs write-back: Ingress should treat `cache:order_draft` as a hot, mutable draft used by bots. Final authoritative writes (order completion) should be committed by ICE.

Recommended order_draft layout (aligned with Custom Bot OOB):
- `cart.items[] {product_id, sku, qty, unit_price_snapshot, total_price, meta}`
- `cart.totals {subtotal, discounts, delivery_fee, tax, grand_total}`
- `cart.status` — building|reserved|checkout_pending|completed|abandoned
- `cart_version` — monotonic int
- `last_price_lock_id` — ICE reservation id

Ingress rules:
- On `add_item`/`update_qty` events: update `cache:order_draft` optimistically and publish to `bot:lane:{bot_type}`. Then optionally trigger ICE preload/reservation for high-value carts.
- For checkout flows, ingress must ensure ICE reservation is requested (or the bot does) before publishing confirm events.
- Respect `cart_version` when applying updates; if version conflict is detected, rehydrate from ICE or the audit stream and retry once.

TTL & retention:
- Order draft TTL: extend for active sessions (e.g., sliding 1h), retention window for abandoned carts (e.g., 7 days) before cleanup.

Observability:
- Emit `ingress.cart.update` events (session_id, event_id, cart_version, change_summary) when updating the order_draft cache.
- Track `ingress.cart.reserve.calls` and `ingress.cart.reserve.failures` for ICE reservation diagnostics.


## ICE Interactions

Hydration and authoritative validation are performed by ICE. Ingress uses a cache-first approach and calls ICE when:

- A required cached blob is missing (`cache:*` key not found).
- A cached blob exists but `schema_version` is outdated or `stale` flag is true.
- Critical authoritative checks are required before a state transition (e.g., checkout finalization, payment verification).

Interaction patterns:

- Synchronous HTTP hydrate (recommended for cache-miss on an inbound event):
  - `POST /hydrate/session` with `{ session_id, user_id, bot_id, event_id, reason }`.
  - Successful response: `200 { hydrated: true, session_blob: {...}, order_draft_blob?: {...} }`.
  - Failure: `5xx` or `4xx` — Ingress may retry once, then fallback to stale cache if acceptable, otherwise move event to `ingress:dlq`.

- Async preload (fire-and-forget): publish `preload:session:{session_id}` or place a message on `ice:preload` stream to allow ICE to prepare snapshots; Ingress sets `preload:pending:{session_id}` marker to avoid duplicate hydrations.

Idempotency: All hydration requests MUST include `event_id` so ICE can detect duplicate requests and return stable responses.

Schema: ICE responses MUST include `schema_version` and `hydrated_at` for each returned blob.

### ICE hydrate — Example requests & responses

1) Synchronous HTTP hydrate (session)

Request (Ingress -> ICE)

```http
POST /api/v1/hydrate/session HTTP/1.1
Host: ice.internal.svc
Content-Type: application/json
Idempotency-Key: evt_20251226_0001

{
  "event_id": "evt_20251226_0001",
  "session_id": "sess_abc123",
  "user_id": "user_789",
  "bot_id": "bot_456",
  "reason": "ingress_cache_miss",
  "required_blobs": ["session","order_draft","bot_meta"]
}
```

Successful Response (200)

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "hydrated": true,
  "session_blob": {
    "session_id": "sess_abc123",
    "user_id": "user_789",
    "bot_id": "bot_456",
    "current_node": "inspect_cart_item",
    "expected_input": "confirmation",
    "schema_version": "1.0",
    "hydrated_at": "2025-12-26T09:12:00Z"
  },
  "order_draft_blob": {
    "order_id": "tmp_ord_987",
    "items": [{"product_id":"p_123","quantity":2,"price_snapshot":120.0}],
    "schema_version": "1.0",
    "hydrated_at": "2025-12-26T09:12:00Z"
  }
}
```

Error Response (transient) — retryable (5xx)

```http
HTTP/1.1 502 Bad Gateway
Content-Type: application/json

{
  "hydrated": false,
  "error": {"code":"ICE_UNAVAILABLE","message":"temporary backend error"}
}
```

Error Response (permanent) — validation fail (4xx)

```http
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json

{
  "hydrated": false,
  "error": {"code":"INVALID_SESSION","message":"session_id not found"}
}
```

2) Async preload (Ingress -> ICE via stream)

Message published to stream `ice:preload` or `ice:requests`:

```json
{
  "request_id": "pre_20251226_01",
  "event_id": "evt_20251226_0002",
  "session_id": "sess_abc124",
  "required": ["session","catalog_snapshot"],
  "requested_by": "ingress",
  "requested_at": "2025-12-26T09:15:00Z"
}
```

ICE will consume this stream and asynchronously write hydrated blobs to the appropriate `cache:*` keys. Ingress should set `preload:pending:{session_id}` when sending this message and clear it when hydration is observed (or after a timeout).

Notes:
- Always include `Idempotency-Key` or `event_id` to allow ICE to dedupe and return stable responses.
- ICE responses MUST carry `schema_version` and `hydrated_at` fields and, when possible, a `source` field indicating whether data came from Postgres JSONB or another authoritative store.


## Failure Handling

- Retries: transient failures (network / 5xx) — retry with exponential backoff up to `N` attempts (configurable, default 3).
- DLQ: after exhausting retries or for permanent validation errors, push the envelope to `ingress:dlq` with diagnostic `error_code`, `attempts`, and `last_error`.
- Stale fallback: if ICE is unavailable and cached blob exists, Ingress may proceed with cached data but must mark `stale: true` and increment `metric.ingress.stale_fallback`.
- Idempotency: use `idempotency:request:{request_id}` keys to prevent duplicate processing of retried inbound events. When an idempotency key exists, return previous outcome or drop duplicate.
- Preload dedupe: use `preload:pending:{session_id}` to avoid concurrent hydrations.
- Audit: every DLQ event must include the inbound raw payload and enrichment state for later replay.

## Observability

Ingress must emit metrics, logs, and traces to enable SLA monitoring and debugging.

- Metrics (counters & histograms):
  - `ingress.inbound.count` — total inbound events by channel
  - `ingress.enrich.success` / `ingress.enrich.fail`
  - `ingress.hydration.calls` and `ingress.hydration.latency` (histogram)
  - `ingress.stale_fallback.count`
  - `ingress.dlq.count`
  - `ingress.publish.latency` (histogram)

- Tracing: propagate `trace_id` through enrichment and ICE calls; create spans for `enrich`, `hydrate`, and `publish`.

- Logs: structured JSON logs including `event_id`, `session_id`, `bot_id`, `user_id`, `attempts`, `error_code`.

Instrument health endpoints and expose a `/metrics` Prometheus scrape endpoint.

---

### Routing recommendation

Recommended behavior: publish directly to `bot:lane:{bot_type}` for lowest latency, and always persist the same canonical envelope to `ingress:resolved_payload` for observability and replay.
