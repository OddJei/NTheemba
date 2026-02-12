````markdown
**Payment + Revenue — Focused Mind Map**

- **Responsibility**: accept payment initiation requests, integrate with `pawapay` provider for deposits/payouts/refunds, process provider callbacks, persist payment records (deposits/payouts/refunds), run reconciliation, and produce payouts/settlements for MSMEs and affiliate pools.

- **Key endpoints (surface)**:
  - `POST /pawapay/deposits/initiate` — initiate a deposit (used by MSME and order-delivery)
  - `POST /pawapay/payouts/initiate` — initiate a payout to a merchant (MSME) or affiliate
  - `POST /pawapay/refunds/initiate` — initiate a refund
  - `/callbacks/pawapay/deposits` — provider callback for deposit events
  - `/callbacks/pawapay/payouts` — provider callback for payout events
  - `/callbacks/pawapay/refunds` — provider callback for refund events
  - Admin endpoints: `GET /admin/platform-balance`, `POST /payout/batch`, `GET /epoch`, `POST /events/msme-payout-initiate`

- **Core flows**:

  - Deposit initiation (`/pawapay/deposits/initiate`):
    - Caller supplies `amount_minor`, `currency`, `phone_number`, `provider`, `order_id`, `business_id`, `metadata`.
    - Service validates ZMW provider/phone for Zambian flows, infers provider if not provided, constructs `pawapay` request, persists `PawaPayDeposit` record, and forwards request to provider client (`pawapay_client`).
    - Returns provider's `external_id`/status; emits audit event and outbox record with `producer: payment-revenue`.

  - Provider callbacks (`/callbacks/pawapay/*`):
    - Current code expects `X-PawaPay-Secret` header if configured (`get_pawapay_webhook_secret`).
    - Payment events are recorded as `PawaPayDeposit`/`PawaPayPayout`/`PawaPayRefund` entries; service maps provider status -> internal status and emits outbox events (`deposit.succeeded`, `deposit.failed`, `payout.succeeded`, etc.).
    - Idempotency: callbacks should include `X-Idempotency-Key` or `event_id`; service deduplicates and persists results to avoid double-processing.

  - Payouts & settlements:
    - MSME payouts: service aggregates eligible settled funds and creates `PawaPayPayout`/`Payout` records; settlement records and `MSMEPayout` objects track batch processing.
    - Affiliate payouts: instead of per-transaction direct commissions, the chosen policy is to create an affiliate pool and distribute from that pool using performance-weighted shares (per your preference). Payment-Revenue must therefore support pool accounting and batch distributions.
    - Payout frequency: preference set to **Immediate (per-order)** — service must support per-order-triggered payout initiation (or allow toggling to batched flows). Ensure safety: prefer idempotent payout initiation and a strong guard against duplicate payouts.

  - Reconciliation:
    - `pawaPay_reconcile` runs periodically (configurable) to fetch provider transactions and reconcile with local `PawaPayDeposit/PawaPayPayout` records; stale transactions older than configured stale seconds are flagged for manual review.
    - Admin endpoints (`/admin/platform-balance`, `/payout/batch`) show balances and allow manual flush/retry.

- **Security & auth**:
  - Middleware skips auth for provider callback paths by design; provider callbacks MUST be verified using HMAC signatures. `X-PawaPay-Secret` fallback is deprecated and should not be relied on for new deployments.
  - Internal endpoints accept `X-Internal-Secret` or `X-Admin-Key` for admin operations; ensure these secrets are rotated and stored securely.

- **Idempotency & events**:
  - Require `X-Idempotency-Key` for all critical externally-initiated requests (deposits/payouts/refunds). Duplicate requests with the same idempotency key must be rejected with a 409 status (do not silently return cached responses).
  - Callbacks should include an `event_id` and `X-Idempotency-Key` where possible; service dedupes on `event_id` but rejects repeated attempts with 409 when the same `X-Idempotency-Key` is seen.

- **Fee & commission handling**:
  - Order-delivery currently computes `platform_fee_amount`/`transaction_fee_pct` and includes these in order metadata. Payment-Revenue should accept these as source-of-truth for computing MSME net amounts and platform revenue splits.
  - Affiliate policy (per your input): no per-transaction direct commissions; instead, maintain an affiliate pool funded from platform revenue and compute affiliate shares via performance-weighted distribution in batch payouts.
  - Config `get_affiliate_commission_share_of_platform_fee` controls what fraction of platform fee goes to affiliate pool; payment-revenue must allocate that portion to the affiliate pool on settlement.

- **Operational concerns & correctness**:
  - Protect against duplicate payouts by requiring idempotency keys and checking for existing `PawaPayPayout` records for the same order/settlement.
  - Per-order immediate payouts increase provider fees and failure surface — consider fallback to queued batch if provider fails and record retry attempts with exponential backoff.
  - Reconciliation must mark stranded funds and produce a small human-review report for mismatches.

- **Observability & tracing**:
  - Propagate `X-Correlation-Id` through provider calls, callbacks, and outbox events; ensure outbox events include `producer: payment-revenue` and `correlation_id`.
  - Emit audit events synchronously for financial state changes (`deposit_initiated`, `deposit_succeeded`, `payout_initiated`, `payout_succeeded`, `refund_initiated`, `refund_succeeded`).

- **Testing recommendations**:
  - Unit tests: deposit initiation happy path and provider error paths, payout initiation idempotency, callback HMAC verification, reconciliation marking mismatches.
  - Integration tests: simulate `pawapay` provider responses and callbacks (success/failure and duplicate callbacks) and verify idempotent processing.
  - Load tests: high-throughput per-order payout mode to ensure batching/retry handles spikes without creating duplicate payouts.

- **Immediate action items / TODOs for code alignment**:
  - Add HMAC verification for provider callbacks and make `X-PawaPay-Secret` a fallback.
  - Implement persisted idempotency records for deposits/payouts/refunds and require `X-Idempotency-Key` on critical endpoints.
  - Add affiliate pool accounting and payout batch logic reflecting performance-weighted distributions.
  - Add tests for per-order payout mode and a safe fallback to batched payout on provider failures.

**S2S Workflows & Automation (Payment-Revenue)**

- **Authoritative signals**: `payment-revenue` is the monetary authority. It emits settlement and pool funding signals after reconciliation.
- **Events to emit via Outbox**:
  - `deposit.succeeded` / `deposit.failed` – for MSME subscription and order deposit lifecycle (include `event_id`, `order_id`, `business_id`, `amount_minor`, `currency`, `occurred_at`, `correlation_id`).
  - `payout.initiated` / `payout.succeeded` / `payout.failed` – for MSME and affiliate payouts (include `payout_id`, `recipient_id`, `amount_minor`, `currency`, `correlation_id`).
  - `epoch_pool_funding` or `pool_balance` – after epoch reconciliation report, publish authoritative `gross_platform_fee`, `gross_subscription_fee`, `GPR`, and computed `pool_amount` for the epoch.
- **Transport & idempotency**: All outbound messages MUST be written to Outbox and dispatched by the OutboxDispatcher. Include `X-Idempotency-Key` and `X-Correlation-Id` in event metadata; persist attempt history for retries.
- **Webhook security**: Verify provider callbacks with HMAC; record verification results in the payment event log. Continue to accept `X-PawaPay-Secret` as fallback only for backward compatibility.
 - **Webhook security**: Verify provider callbacks with HMAC only; do not accept `X-PawaPay-Secret` except during an explicit short-term migration window. Document the migration window separately.
- **Consumption expectations**: `affiliate-engine` will consume only `epoch_pool_funding`/`pool_balance` for authoritative pool amounts and `deposit.succeeded` for subscription revenue when evaluating GPR. `order-delivery` remains the authoritative source for `delivery_confirmed` events used for paid attribution.

````
**Payment & Revenue — Focused Mind Map**

- **Responsibility**: Handle payment requests, process provider callbacks, compute fee splits (platform, affiliate, MSME), persist settlement ledger.

- **Key endpoints**:
  - `POST /v1/payments/initiate` — start payment (OrderDelivery calls)
  - `POST /v1/payments/callback` — provider callback (PawaPay)
  - `GET /v1/settlements/{order_id}` — fetch settlement

- **Fee rules**:
  - Source MSME fee/commission rules from MSME Engine at payment time (dynamic lookup).
  - Compute split: platform fee, affiliate commission, MSME net.
  - Persist settlement idempotently keyed by `order_id`.

- **Failure handling**:
  - If PawaPay fails, retry automatically (policy) then mark payment failed and surface manual payment options.
  - Support manual mark-as-paid by admin if necessary.

- **Settlement model (example)**

```json
{
  "order_id":"ORD-123",
  "gross_amount":500,
  "platform_fee":25,
  "affiliate_commission":50,
  "msme_net":425,
  "status":"settled"
}
```

- **Mermaid flow**:

```mermaid
flowchart TD
  A[Order -> Payment Initiate] --> B[PawaPay Gateway]
  B --> C[Callback -> PaymentRevenue]
  C --> D[Lookup MSME Fee Rules]
  D --> E[Compute Settlement -> Persist]
  E --> F[Emit events (order_paid, affiliate_sale)]
```

- **Operational notes**:
  - Keep idempotency keys for provider callbacks.
  - Audit every settlement in Audit service.
