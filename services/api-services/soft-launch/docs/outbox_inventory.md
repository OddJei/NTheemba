# Outbox Inventory (service-by-service)

This document lists discovered outbox topics, destinations, and example payload shapes discovered by scanning the codebase.

**msme-engine**
- Topics:
  - `notification.{channel}`
    - Destination: `<notification_service>/notification/send`
    - Payload keys: `user_id`, `business_id`, `channel`, `payload` (template-specific)
    - Example usage: in-app notifications via `emit_notification_outbox`
  - `deposit_requested`
    - Destination: Payment-Revenue `/pawapay/deposits/initiate`
    - Payload keys: `subscription_id`/`order_id`, `business_id`, `amount_minor`, `currency`, `phoneNumber`, `paymentType`, `metadata`
  - `msme_referral`
    - Destination: Affiliate referral endpoint (configurable)
    - Payload keys: `event_id`, `event_type`, `occurred_at`, `deposit_id`, `affiliate_id`, `business_id`, `amount_zmw`, `correlation_id`, `meta`
  - NOTE: removed: `pawapay.deposit.callback` and `payment_success` — these were previously documented as forwarded summaries to `affiliate-engine` but we will instead describe canonical outbox payloads below for the target services (notification, deposit initiator, and payment callbacks).

**order-delivery**
- Topics:
  - `notification.{channel}`
    - Destination: Notification service
    - Payload keys: `user_id`, `business_id`, `channel`, `payload`
  - `deposit_requested`
    - Destination: Payment-Revenue `/pawapay/deposits/initiate`
    - Payload keys: `order_id`, `business_id`, `amount_minor`, `currency`, `phoneNumber`, `paymentType`, `metadata` (includes `source: order_delivery`)
  - `payout_requested`
    - Destination: Payment-Revenue `/msme/payouts/initiate`
    - Payload keys: `order_id`, `business_id`, `msme_phone`, `order_amount_minor`, `currency`, `metadata`
  - `refund_requested`
    - Destination: Payment-Revenue `/pawapay/refunds/initiate`
    - Payload keys: `order_id`, `business_id`, `amount_minor`, `currency`, `payment_method`, `reason`, `correlation_id`

**payment-revenue**
- Topics:
  - `pawapay_deposit_initiator` (initiator callback)
    - Destination: initiating service `/callbacks/payments/deposits` (msme, order-delivery, affiliate — inferred per initiator)
    - Payload keys: `event_id`, `event_type` (`payment_success`/`payment_failed`), `payment_id`/`depositId`, `order_id`, `business_id`, `amount`, `amount_minor`, `currency`, `status`, `meta`, `provider`, `provider_transaction_id`, `correlation_id`
  - `pawapay_payout_initiator`
    - Destination: initiating service `/callbacks/payments/payouts`
    - Payload keys: `event_id`, `event_type` (`payout_success`/`payout_failed`), `payout_id`, `order_id`, `business_id`, `amount`, `currency`, `meta`, `provider`, `correlation_id`
  - `pawapay_refund_initiator`
    - Destination: initiating service `/callbacks/payments/refunds`
    - Payload keys: `event_id`, `event_type` (`refund_success`/`refund_failed`), `refund_id`, `deposit_id`, `order_id`, `business_id`, `amount`, `currency`, `meta`, `correlation_id`
  - `notification`
    - Destination: Notification service `/notification/send`
    - Payload keys: `channel`, `user_id`, `business_id`, `template`, `payload`
  - `payment_*` internal events delivered via HTTP or outbox by decision in code (e.g., `payment_success` flows trigger affiliate dispatch)

**affiliate-engine**
- Topics:
  - `order.delivered` / `order.confirmed`
    - Destination: Order-Delivery `/events/order/delivered` and `/events/order/confirmed`
    - Payload keys: `order_id`, `total_amount` (major units), `affiliate_id`, `user_phone` or `user_id`, `business_id`, `occurred_at`, `meta`, `session_id`
    - Affiliate behaviour: when received `affiliate-engine` will:
      - create an `AffiliateEvent` of type `sale` and persistent attribution when applicable;
      - increment the affiliate's `sales_volume` by `total_amount` for the current epoch;
      - increment `unique_buyers` for the epoch if this buyer (by `user_phone`/`user_id`) is new to the affiliate during the epoch.

  - `session_cycle_created` / `session_cycle_*` (from Bot-Session / ICE)
    - Destination: Affiliate `/events/session-cycle-created`
    - Payload keys: `event_id`, `producer`, `affiliate_id`, `session_id`, `cycle_id`, `cycle_state`, `user_phone`, `business_id`, `occurred_at`, `meta`
    - Affiliate behaviour: increments `session_cycles` for the affiliate in the current epoch when a cycle-created event is received.

**bot-session**
- Topics:
  - `session_cycle_created` (topic `session_cycle_created`)
    - Destination: Affiliate `/events/session-cycle-created`
    - Payload keys: `event_id` (cycle id), `event_type` (`session_cycle_created`), `occurred_at`, `producer`, `affiliate_id`, `session_id`, `cycle_id`, `cycle_state`, `user_phone`, `business_id`, `meta`

**ice**
- Topics:
  - `ice.cycle.upgraded`
    - Destination: Bot-Session `/events/ice.cycle.upgraded` or `outbox-dispatcher`
    - Payload keys: `session_id`, `cycle_id`, `new_stage`, `snapshot`, `event_id`, `initiated_by`, `timestamp`
  - `ice.cycle.created`
    - Destination: Bot-Session `/events/ice.cycle.created` or `outbox-dispatcher`
    - Payload keys: `session_id`, `cycle_id`, `cycle_state`, `event_id`, `idempotency_key`, `initiated_by`, `timestamp`
  - `ice.confirmed`
    - Destination: `outbox-dispatcher` (or bot-session fast-post)
    - Payload keys: `session_id`, `order_id`, `affiliate_id`, `amount_minor`, `timestamp`

**cart**
- Topics:
  - Generic via `add_outbox_event` — producer `cart`.
    - Typical payload shapes vary; helper inserts `event_type` and a payload object including `business_id`, `entity_type`, `entity_id`, `meta`.
    - Example callers currently emit audit events; specific topic names are application-defined.

**catalog-inventory**
- Topics:
  - Generic via `add_outbox_event` — producer `catalog-inventory`.
    - Typical payload: `{ event_type, business_id, entity_type, entity_id, source, meta }`.
    - Used for inventory change events / inventory updates.

Canonical payload schemas (target services)

- `notification` (Notification service `/notification/send`)
  - Common fields:
    - `channel`: one of `whatsapp`, `email`, `push` (string)
    - `user_id`: optional string
    - `business_id`: optional string
    - `template`: optional template name (string)
    - `payload`: channel-specific object
  - Email payload (required keys):
    - `to`: recipient email (string)
    - `subject`: email subject (string)
    - `message` or `html`: message body (string)
  - WhatsApp payload (required keys):
    - `to`: recipient phone number (string)
    - `message` or `text`: message text (string)
    - Example outbox payload used by `notification` service (whatsapp outbox record):
      ```json
      {
        "request_id": "ntf_...",
        "to": "+2609...",
        "from": null,
        "text": "Your code is 1234",
        "meta": { "platform": "whatsapp", "business_id": "..." }
      }
      ```

- `deposit_requested` (Payment-Revenue `/pawapay/deposits/initiate` — emitted by `msme-engine`)
  - Canonical payload (subscription deposit initiation):
    - `subscription_id`: optional string
    - `business_id`: string
    - `amount_minor`: integer (minor units, e.g., cents)
    - `currency`: string (e.g., `ZMW`)
    - `phoneNumber`: optional string (payer phone)
    - `paymentType`: string (for subscription flows use `subscription`)
    - `metadata`: object (recommended keys: `source`, `correlation_id`, `initiator_id`)
  - Example:
      ```json
      {
        "subscription_id": "sub_...",
        "business_id": "biz_...",
        "amount_minor": 5000,
        "currency": "ZMW",
        "phoneNumber": "+2609...",
        "paymentType": "subscription",
        "metadata": { "source": "msme_engine", "correlation_id": "..." }
      }
      ```

- `pawapay_deposit_initiator` (Payment-Revenue → initiating service callback `/callbacks/payments/deposits`)
  - Payment-Revenue enqueues a single unified callback to the initiating service. Canonical keys (as emitted by `payment-revenue`):
    - `event_id`: string (e.g., `deposit-{deposit_id}`)
    - `event_type`: `payment_success` or `payment_failed`
    - `occurred_at`: ISO8601 timestamp
    - `correlation_id`: optional string
    - `producer`: `payment-revenue`
    - `payment_id` / `depositId`: string (deposit identifier)
    - `amount_minor`: integer
    - `amount`: float (major units)
    - `order_id`: optional string
    - `business_id`: optional string
    - `currency`: string
    - `provider`: optional string (payment provider)
    - `provider_transaction_id`: optional string
    - `platform_fee_minor`: integer
    - `fee_bps`: integer | null
    - `payment_type`: string
    - `msme_net_minor`: integer
    - On failure: `failure_code`, `failure_message`, and optional `response`/`meta`.
  - Example success callback:
      ```json
      {
        "event_id": "deposit-...",
        "event_type": "payment_success",
        "occurred_at": "2026-02-17T12:00:00Z",
        "correlation_id": "...",
        "producer": "payment-revenue",
        "payment_id": "d_...",
        "depositId": "d_...",
        "amount_minor": 5000,
        "amount": 50.0,
        "order_id": "ord_...",
        "business_id": "biz_...",
        "currency": "ZMW",
        "provider": "pawapay",
        "provider_transaction_id": "prov_tx_...",
        "platform_fee_minor": 500,
        "fee_bps": 100,
        "payment_type": "subscription",
        "msme_net_minor": 44500,
        "meta": {}
      }
      ```

Notes & conventions observed
- All services now write into `public.outbox` via `libs/outbox/outbox.py` helper in many places — helper usage is preferred to ensure consistent columns (topic, payload, destination, correlation_id, idempotency_key/dedupe_key, producer).
- Destinations are often explicit full URLs (e.g., `http://affiliate-engine:8510/events/...`) or logical `outbox-dispatcher` for central dispatching.
- Idempotency keys are often set to generated UUIDs or derived event ids (e.g., `deposit:{deposit_id}:initiator`).
- Notification usage is common (topic `notification` or `notification.{channel}`) with destination `notification/send`.

Additional services scanned

- **outbox-dispatcher**
  - Role: Dispatcher/poller that reads `public.outbox` (DB mode) or polls service `/outbox/pending` endpoints.
  - Endpoints / behaviour:
    - Reads pending rows from `public.outbox` when `OUTBOX_USE_DB=1`.
    - Posts `payload` to `destination` and acks by updating `public.outbox` status (`sent`/`failed`) and `attempts`.
    - Uses `dedupe_key` as `X-Idempotency-Key` when dispatching.

- **notification** (Node service)
  - Role: delivery target for `notification` events; not a producer.
  - Routes: `/notification/send` accepts payloads with keys: `channel`, `user_id`, `business_id`, `template`, `payload`.
  - Notes: implementation lives in `services/notification` (Node); no Python outbox writes discovered.

- **audit-service**
  - Role: records audit logs; not an outbox producer.
  - Routes: `/audit` (router) and `/health`.
  - Notes: audit entries are emitted by other services using `audit_client` and stored/forwarded by this service.

- **delivery**
  - Role: placeholder in repo; `services/delivery/src` appears empty in this workspace snapshot.
  - Notes: no outbox writes discovered.

- **frontend**
  - Role: client UI; not an outbox producer.

Scan status
- Completed: repository scanned for `create_outbox_row`, legacy `Outbox`/`OutboxEvent` insertions, and `/outbox/pending` endpoints across services.
- Remaining: a few legacy models remain in service `models.py` files for compatibility and tests; no additional active outbox producers were found beyond the services already documented above.

Next steps
- I can: (A) expand this doc with example JSON payloads per topic, (B) generate Pydantic schemas for target events and add them under `libs/outbox/schemas` or per-service `src/app/schemas.py`, or (C) prepare a migration script to move pending rows from legacy per-service tables into `public.outbox`. Which should I do next?
