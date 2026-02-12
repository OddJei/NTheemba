**Separation of Concerns — Cart / Catalog / Order-Delivery / Payment-Revenue / Affiliate**

Purpose: clearly assign responsibilities to services to avoid overlapping responsibilities and ensure reliable, auditable financial and attribution flows.

1) Order-Delivery
- Authoritative source for order lifecycle and order-level metadata (status, total_amount, currency, affiliate_code, affiliate_id when present).
- Responsibilities:
  - Create `order` records and compute `platform_fee_amount` / `transaction_fee_pct` and include in `order.meta`.
  - Emit `order_created` outbox events containing affiliate fields when present; include `event_id` and `correlation_id`.
  - Expose `mark_paid` and `initiate_payment` endpoints; call `payment-revenue` to initiate payments but do not perform settlement.
  - Initiate delivery lifecycle and emit `order_delivered` / `delivery_confirmed` outbox events.

2) Payment-Revenue
- Authoritative source for money-in/money-out, pool accounting, reconciliation, and initiating payouts via provider clients.
- Responsibilities:
  - Handle `pawapay` deposit/payout/refund integrations, provider callbacks, and reconciliation.
  - Persist `PawaPayDeposit`/`PawaPayPayout`/`PawaPayRefund` records and expose admin endpoints for balances and manual batch payouts.
  - Accept `order` metadata (fees) from order-delivery and allocate the platform fee share to system revenue and to the affiliate pool according to configured `pool_pct`.
  - Maintain affiliate pool ledger (funding, allocations, disbursements) and produce `payout` requests to `pawapay` when instructed by affiliate-engine (or when configured to pay directly from payment-revenue).
  - Expose idempotent endpoints for deposit/payout initiation; require `X-Idempotency-Key` and verify callback authenticity (HMAC preferred, `X-PawaPay-Secret` fallback).

3) Affiliate-Engine
- Authoritative for attribution computation, epoch-based pool distribution, and initiating affiliate payout requests (via `payment-revenue`).
- Responsibilities:
  - Ingest `order_created` and `order_delivered` events (via outbox dispatcher) and compute attributions/click associations.
  - Maintain epoch windows (configurable) and compute metrics, weighted scores, and payout allocations per epoch.
  - Generate `affiliate_payout` batches (or create a request to `payment-revenue` to execute payouts). Keep event-based records for audits.
  - Do not execute low-level provider calls itself; delegate actual fiat payouts to `payment-revenue` (calls or outbox events).

4) Bot-Session
- Authoritative for session cycles and best-effort affiliate attribution hints.
- Responsibilities:
  - Persist `SessionStateCycle` with `affiliate_id`/`affiliate_code` when a cycle was initiated via an affiliate link.
  - Enrich `order` creation flows indirectly (order-delivery can query latest cycle if `session_id` provided) but not be the source-of-truth for final financial attribution.

5) Outbox Dispatcher
- Reliability layer for cross-service delivery.
- Responsibilities:
  - Read `OutboxEvent` (or equivalent) records and deliver to destination services (affiliate-engine, payment-revenue, notification, etc.) with idempotency and retries.
  - Prefer outbox delivery over synchronous HTTP posts from producers for any business-critical event that must not be lost.

Design rules / contracts:
- Single Source of Truth: money movements — `payment-revenue`. Order metadata — `order-delivery`. Attribution calculations and pool decisions — `affiliate-engine`.
- Idempotency: require `X-Idempotency-Key` on critical endpoints and persist keys. Callbacks must include `event_id` or be signed; service must dedupe by persisted keys/external ids.
- Correlation: propagate `X-Correlation-Id` across all inter-service calls and include in outbox events and audit traces.
- Minimal synchronous coupling: producers should write outbox events for downstream consumers; avoid direct synchronous calls when the action is financial-critical.
- Clear ownership for payouts: `affiliate-engine` computes allocations and requests `payment-revenue` to execute payouts; `payment-revenue` performs reconciliation and records provider-level status.

Operational notes:
- Monitoring: track outbox backlog, reconcile failures, and payout success rates.
- Security: HMAC-signed provider callbacks, rotate internal secrets, and require `X-Internal-Secret` or scoped JWTs for internal endpoints.
- Testing: contract tests for outbox payload shape (affiliate fields), idempotency and reconciliation jobs.

This file should be referenced in planning documents and PRs that touch cross-service financial or attribution code.
