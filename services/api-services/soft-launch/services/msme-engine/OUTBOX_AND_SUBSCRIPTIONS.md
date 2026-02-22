# Outbox and Subscription / Payment flow

This document describes how subscription and payment flows interact with the
Outbox pattern in `msme-engine`.

- Endpoints
  - `POST /business/{id}/subscribe` — starts a subscription flow. For paid
    plans this is a lightweight initiation and may not contact payment-revenue.
  - `POST /business/{id}/subscribe_and_pay` — initiates a subscription and,
    when `amount_minor` and `phone_number` are provided, initiates a payment
    deposit. The service will emit a Payment Initiation Outbox event that the
    Outbox dispatcher will deliver to the configured `payment-revenue` target.

- Security
  - Payment-initiating requests MUST include an `Authorization: Bearer <token>`
    header containing a valid access token signed with `MSME_JWT_SECRET`.
  - Internal read endpoints such as `/outbox/pending` require `X-Internal-Secret`.

- Behavior guarantees
  - The `subscribe_and_pay` path persists a local `PaymentInitiation` record
    and then emits an outbox event (via `emit_subscription_deposit_request`).
  - The response for `subscribe_and_pay` may include a `payment_revenue_response`
    structure containing the locally recorded `initiated_event_id` returned when
    the outbox row was created.

- Implementation notes
  - Code path: `services/msme-engine/src/app/main.py` calls
    `emit_subscription_deposit_request` (helpers in `src/app/helpers/payment_helpers.py`) which creates the Outbox row.

- Troubleshooting
  - If the outbox row is not visible from `/outbox/pending`, verify the
    database schema includes the canonical `public.outbox` table or that the
    environment's outbox helper is configured for the active SQL dialect.
