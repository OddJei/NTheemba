Refactor Roadmap — Outbox-first Migration & Attribution Hardening
=================================================================

Goal
----
Move authoritative publishes and attribution flows to an Outbox-first pattern, forward MSME JWTs for attribution, enforce HMAC callbacks for payment callbacks, and align cache TTLs and idempotency for financial writes.

Scope (services)
-----------------
- `msme-engine`, `ice-service`, `outbox-dispatcher`, `payment-revenue`, `order-delivery`, `affiliate-engine`, `cart`, `catalog-inventory`, `notification`, `bot-session`, `audit-service`, OOB (Redis)

Phases (high level)
--------------------

Phase 0 — Discovery & Short-term Guards (now)
- Audit existing Outbox models and dispatcher endpoints in each service.
- Add request/response tests to assert `X-Correlation-Id` and `X-Idempotency-Key` presence.
- Lock down `OUTBOX_INTERNAL_SECRET` usage for dispatcher endpoints (already present in some services).

Phase 1 — Shared Outbox & Helpers (small PRs)
- Add a small shared helper (library snippet) for writing `OutboxEvent` rows with fields: `id`, `event_type`, `payload JSONB`, `correlation_id`, `idempotency_key`, `status`, `send_after`, `attempts`, `created_at`.
- Add client helpers for: create_outbox(tx, event_type, payload, correlation_id, idempotency_key).
- Add standard dispatcher headers contract: `X-Internal-Secret`, `X-Idempotency-Key`, `X-Correlation-Id`.

Phase 2 — ICE: Authoritative Outbox Writes
- In `ICE` replace direct authoritative Redis stream publishes for `ice.hydrated`, `ice.reserved`, `ice.confirmed` with Outbox writes inside same DB transaction that persists state.
- Keep current Redis stream publishers as a temporary sink consumed by legacy consumers; OutboxDispatcher will also POST to Redis stream if needed.
- Add unit and integration tests verifying Outbox rows are created on hydrate/reserve/confirm.

Phase 3 — MSME: Payment / JWT Forwarding
- Ensure `msme-engine` forwards incoming Authorization bearer tokens when calling `payment-revenue` and other attribution-sensitive services.
- Add `affiliate_id` claim naming and ensure adapters read and forward it.
- On payment success callbacks, lookup `PaymentInitiation` by `reference_id/depositId` and write `msme.subscription.payment_succeeded` to Outbox (only when affiliate present or always, per policy).

Phase 4 — Payment-Revenue: HMAC-only Callbacks
- Add HMAC signing in `payment-revenue` callbacks (header `X-Payment-Signature` HMAC-SHA256) and verification middleware in `msme-engine` and other receivers.
- Store secret in env `PAYMENT_REVENUE_HMAC_SECRET` or Vault; update tests.

Phase 5 — Downstream Migration (Order-Delivery, Affiliate, Cart)
- Update `order-delivery`, `cart`, and `affiliate-engine` to accept events from OutboxDispatcher `/outbox/pending` and `/outbox/ack` endpoints protected by `OUTBOX_INTERNAL_SECRET`.
- Ensure `order-delivery` writes authoritative `delivery_confirmed` Outbox events with `affiliate_id`, `order_id`, `amount_minor`, `correlation_id`.
- `affiliate-engine` should dedupe by `event_id` and idempotently credit pools only after payment-revenue pool signals if needed.

Phase 6 — Cache TTL Alignment & Invalidation
- Standardize `businessdetails:{phone}` TTL to 24h in `msme-engine` and consumers (ICE, bot-session).
- Ensure `msme.business_updated` Outbox events trigger cache invalidation in consumers.

Phase 7 — Idempotency & DB Constraints
- Add DB idempotency records and/or unique constraints to prevent double-commits for `subscribe_and_pay`, deposit initiation, payout execution.
- Use `X-Idempotency-Key` and `event_id` to coalesce retries.

Phase 8 — Dispatcher Hardening & Observability
- Improve `outbox-dispatcher` with exponential backoff, DLQ marking after N attempts, and metrics (attempts, success, failure, latency).
- Ensure dispatcher attaches `X-Internal-Secret`, `X-Idempotency-Key`, and `X-Correlation-Id` to target calls.

Phase 9 — Integration Tests & Rollout
- Add end-to-end tests for:
  1. `subscribe_and_pay` -> `payment-revenue` initiate -> signed callback -> MSME writes Outbox `msme.subscription.payment_succeeded` -> `affiliate-engine` receives via dispatcher.
  2. ICE `confirm` -> Outbox row created -> dispatcher delivers to `order-delivery` and `payment-revenue` (with forwarded Authorization).
- Rollout plan: feature-flag Outbox-first in ICE; run dispatcher in proxy mode to mirror events to legacy Redis streams; flip consumers to Outbox endpoints; remove stream reliance.

Concrete First PRs (priority)
-----------------------------
- PR 1 (small): Add `docs/refactor-roadmap.md` + TODO tracker (this file).
- PR 2 (small): Shared Outbox helper + tests (add to `msme-engine` or `shared-lib`).
- PR 3 (ICE): Write Outbox row for `confirm` in same tx; keep Redis stream write for compatibility; add tests.
- PR 4 (MSME): Add HMAC verification middleware & unit tests for payment callbacks.
- PR 5 (Dispatcher): Improve retry/DLQ and ensure headers are set according to contract.

Migration Safety Notes
----------------------
- Do not remove Redis stream sinks until consumers are migrated and validated.
- Use `send_after` on Outbox rows to intentionally delay some events if needed.
- Add a compatibility mode where dispatcher mirrors Outbox events to existing streams during cutover.

Where I saved this
------------------
- Roadmap: [docs/refactor-roadmap.md](docs/refactor-roadmap.md)

Next steps I can take now
------------------------
- Open PR to implement PR 2 (shared Outbox helper) in `msme-engine` or create a `libs/outbox` helper.
- Or generate the ICE PR (PR 3) patch that writes Outbox in `confirm` path.

