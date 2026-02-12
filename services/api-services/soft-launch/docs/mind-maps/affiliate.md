````markdown
**Affiliate Engine — Focused Mind Map (Updated)**

- **Chosen responsibilities**: maintain pools & payouts, compute epoch-weighted distributions, accept events via outbox dispatcher, expose reports and payout batches.

- **Outbox-first integration**: persist affiliate events and signals to the local Outbox within the same transaction as attribution writes; rely on OutboxDispatcher for delivery to sinks (see docs/mind-maps/outbox-integration.md).

- **Key endpoints / inputs**:
  - `POST /events/order/created` (via outbox) — ingest order metadata (includes `affiliate_code`, `affiliate_id`, `event_id`, `correlation_id`, `order_id`, `business_id`, `total_amount`, `metadata`).
  - `POST /events/order/delivered` — mark sale events as delivered and finalize attributions.
  - `POST /token/resolve` — resolve short-lived affiliate tokens from links (single-use semantics).
  - Admin: `GET /pool/standing`, `POST /pool/allocate`, `POST /epochs/{id}/close` (manage epochs and allocations).

- **High-level flow**:
  - Ingest `order_created` outbox from `order-delivery` (authoritative for affiliate fields). If `affiliate_code` absent, optionally query `bot-session` for latest cycle (best-effort enrichment).
  - Record `AffiliateEvent` rows for sales; create `AffiliateAttribution` linking sale to affiliate when applicable.
  - During epoch end: compute metrics (sales_volume, unique_buyers, paid_attributions, session_cycles, clicks), compute weighted scores, and allocate pool funds.
  - Emit `affiliate_payout_request` events (or call `payment-revenue` via its idempotent payout endpoint) to disburse funds from affiliate pool.

- **Payout model**:
  - Pool funding: platform fee portion allocated to affiliate pool is recorded/credited by `payment-revenue` during settlement (payment-revenue is the monetary authority). Affiliate-engine relies on pool balance info (via outbox or admin API) to schedule payouts.
  - Payout frequency: configurable epochs (you selected custom epochs). Default behavior: epoch-based aggregation and batch payout.
  - Payout initiation: affiliate-engine constructs batch payout payloads (affiliate_id, amount_minor, metadata) and posts to `payment-revenue` `POST /pawapay/payouts/initiate` (idempotent, requires `X-Idempotency-Key`).

- **Delivery & attribution**:
  - `order-delivery` is the authoritative attach-point for affiliate metadata on orders; affiliate-engine treats bot-session inputs as supplemental hints only.
  - When `order_delivered` is received, mark attributions as `delivered` so they qualify for payout.

- **Reliability & delivery**:
  - Use outbox dispatcher for delivery of `order_created` and `order_delivered` events into affiliate-engine; do not rely on direct HTTP posts for critical event delivery.
  - Idempotency: require `event_id` and/or `X-Idempotency-Key` on incoming events; dedupe by persisted event_id.

- **Security & tokens**:
  - Affiliate link tokens: short TTL, single-use tokens; token resolution endpoint returns affiliate_id and optional metadata.
  - Admin operations require `Authorization` and `X-Admin-Key` as configured.

- **Observability & audit**:
  - Emit audit events for epoch close, allocation, and payout requests. Include `correlation_id` in all admin and payout-related events for traceability.

- **Tests & validation**:
  - Unit tests for allocation math, epoch closing, and idempotent payout generation.
  - Integration tests: outbox delivery -> event ingestion -> attribution -> epoch close -> payout_request -> payment-revenue mock.

- **Potential improvements / TODOs**:
  - Add explicit `pool_balance` outbox event from `payment-revenue` after settlement so affiliate-engine can reconcile available funds.
  - Add webhook or push notification from `payment-revenue` to affiliate-engine for payout success/failure callbacks to mark affiliate payout records.

````

**S2S Workflows & Automation (Updated)**

- Emit strategy: Affiliate Engine will only process `delivery_confirmed` events for sale qualification and payout eligibility (i.e., no longer require `order_created` or `order_paid` events for payout computation). `order_created`/`order_paid` remain useful for dashboards but are not essential for pool allocations.
- Sources of events:
  - `order-delivery` -> Outbox -> `affiliate-engine`: on `delivery_confirmed` include `order_id`, `affiliate_id`/`affiliate_code`, `business_id`, `total_amount`, `currency`, `occurred_at`, and `correlation_id`.
  - `msme` subscription payments -> Outbox -> `affiliate-engine`: when a subscription payment succeeds emit `msme.subscription.payment_succeeded` with `business_id`, `amount_minor`, `subscription_id`, `occurred_at`, and `correlation_id`.
  - `bot-session` -> Outbox -> `affiliate-engine`: continue to emit `session_cycle_created` for cycles initiated by affiliates (used for supplemental attribution enrichment).
- Delivery-only policy rationale: reduces double-counting and ensures attributions are only credited when delivery confirmation completes the commerce lifecycle. Affiliate-engine will mark events as `delivered` and use them for epoch computations.
- Transport & reliability: all inter-service messages MUST flow through the Outbox Dispatcher (no direct synchronous posts for these critical events). Outbox events must include `event_id` and `X-Correlation-Id` and honor idempotency keys.
- Pool funding signals: `payment-revenue` will publish `epoch_pool_funding` or `pool_balance` outbox events after reconciliation/settlement so `affiliate-engine` can read authoritative `gross_platform_fee`, `gross_subscription_fee`, `GPR`, and `pool_amount` for the epoch.

```
**Affiliate Engine — Focused Mind Map**

- **Responsibility**: Manage affiliate creation, link generation/resolution, token attribution (short-lived tokens), click tracking, conversion attribution, metrics, pool allocation and payouts.

- **Key endpoints / topics**:
  - `POST /v1/affiliate/links` — create campaign link
  - `GET /a/{affiliate_code}/resolve` — resolve affiliate link and create short-lived token
  - `POST /token/resolve` — resolve short-lived token into affiliate attribution (single-use)
  - `POST /events/order/delivered` — ingest delivery events to mark attributions delivered
  - Pool / epoch endpoints: manage epochs, compute payouts, view standings

- **Token & Attribution rules (code-aligned)**:
  - Tokens generated on link resolve are intentionally short-lived (configured by `get_affiliate_token_ttl_seconds`) and intended for immediate use in chat flows.
  - Tokens are single-use: `token_row.used` is marked on successful resolve (prevents reuse).
  - Token resolution validates caller `business_id` (from MSME-issued S2S tokens) and ties buyer/session metadata into token `meta` for audits.
  - On token resolve, `AffiliateEvent` rows are persisted (outbox pattern) to record `campaign_click` / `token_resolved` events.

- **Metrics, pooling & payouts**:
  - Metrics computed per epoch include GMV, unique buyers, referrals, clicks and paid attributions.
  - Weighted scoring and OP score computation is performed by `src/app/pool.py` functions (see `compute_weighted_scores`, `compute_op_scores`).
  - Payout cadence is monthly by default; payout execution is expected to require admin approval before bulk execution (current behavior).

- **Event delivery / outbox**:
  - Affiliate events are stored in `AffiliateEvent` and dispatched reliably via `outbox_dispatcher.py` which polls undispatched events and POSTs them to the configured `EVENT_SINK_URL`.
  - This outbox ensures resilient delivery with retries and marks `dispatched_at` on success.

- **Mermaid flow (core interactions)**:

```mermaid
flowchart TD
  User -->|click link| AffiliateEngine
  AffiliateEngine -->|create token| Bot/ICE
  Bot -->|resolve token (POST /token/resolve)| AffiliateEngine
  AffiliateEngine -->|persist AffiliateEvent| DB
  OutboxDispatcher -->|POST event| EventSink
  OrderService -->|delivery callback| AffiliateEngine
  AffiliateEngine -->|mark attribution delivered| DB
```

- **Plain English Flows**

- **Link resolve & token generation**
  - A user clicks an affiliate link. The affiliate engine validates the link and business/product (via MSME and Catalog) and generates a short-lived token. The token (prefixed) and a WhatsApp prefill URL are returned for the bot to share with the buyer.

- **Token resolve (single-use)**
  - When the buyer posts the token back (via a bot), the bot calls `POST /token/resolve` with the token and optional session/buyer info. Affiliate Engine validates the token, marks it as used, persists an `AffiliateEvent` (`token_resolved`/`campaign_click`), and returns product/affiliate attribution to the bot.

- **Order/delivery attribution**
  - When an order is created/delivered, Order-Delivery posts delivery events to `POST /events/order/delivered`. Affiliate Engine updates corresponding `AffiliateEvent` rows (sets `delivered_at`) and marks attribution status to `delivered` so that sales are eligible for payouts.

- **Payouts & pool computation**
  - At epoch close, metrics are computed and payouts allocated using `compute_payouts`. Admins review monthly payout previews and then trigger payout execution (bulk payout requires approval in current flow).

- **Operational notes / recommendations**
  - Short TTL single-use tokens improve security and limit stale attribution.
  - Use the outbox dispatcher for reliable event delivery; monitor `AffiliateEvent.dispatched_at` and sink health.
  - Keep click logs and token `meta` for audits and dispute resolution.
  - Background jobs to maintain/monitor:
    - Outbox dispatcher (exists) — ensure it's running as a service.
    - Epoch closer / pool allocator (periodic job to close epochs and compute allocations).
    - Payout executor (admin-triggered or scheduled worker to process payout batches).
    - Metrics snapshotter / retention cleaner (archive old metrics/events).

- **Testing notes**
  - Tests should cover token generation/resolve edge cases (expired, used, business mismatch), idempotency of event ingestion, outbox delivery behavior, and pool calculation correctness.

