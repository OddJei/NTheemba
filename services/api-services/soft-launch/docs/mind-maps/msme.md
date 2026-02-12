**MSME Engine — Focused Mind Map**

- **Responsibility**: Business and user identity, entitlements, fee rules, bot metadata, short‑lived tokens, service‑to‑service auth, subscription management and payment event handling.

- **Outbox-first integration**: write notification and lifecycle intents to the local Outbox in the same transaction as state changes; use the OutboxDispatcher to deliver events reliably (see docs/mind-maps/outbox-integration.md).

- **Key endpoints**:
  - `GET /v1/business/phone/{phone}` — resolve business by phone (returns business + owner info)
  - `GET /v1/business/{id}/bot_metadata` — returns `bot_type`, entitlements
  - `GET /v1/fees/{business_id}` — fee and commission rules
  - `POST /v1/tokens/shortlived` — generate short‑lived tokens for affiliate resolution
  - `POST /business/{id}/subscribe` — initiate/record subscription
  - `POST /business/{id}/subscribe_and_pay` — initiate subscription and (optionally) payment via payment-revenue
  - `POST /events/payment_success` — idempotent handler for payment success
  - `POST /events/payment_failed` — idempotent handler for payment failures

- **Behavior / policies**:
  - Provide `bot_type` (used by ICE); allowed values: `default` or `custom`. If missing, ICE falls back to `default`.
  - Store dynamic fee rules used at payment time; expose via `GET /v1/fees/{business_id}`.
  - Emit `MsmeEvent` records for important lifecycle changes (onboarding, subscription changes, payment events). These are persisted with `event_id` and used for audit/consumers.

- **Service-to-Service (S2S) token policy**:
  - Tokens issued by MSME (via normal auth flows or `POST /auth/service-token/{business_id}`) include the following claims for downstream authorization:
    - `sub`: user id
    - `role`: role name (e.g., `admin`, `msme`, `affiliate`, `staff`, `default`)
    - `business_id`: the business context the token represents
    - `affiliate_id`: optional (when applicable)
    - `iat`, `exp`, `typ`
  - Downstream services should rely on `business_id` + `role` + `sub` for authorization decisions.
  - Example: `issue_access_token()` encodes `{"sub": <user.id>, "role": <role>, "business_id": <business.id>, ...}`.

- **Caching strategy (business lookups)**:
  - Cache key: `businessdetails:{phone}`
  - TTL: long (24h) for read-heavy lookups; invalidate on business updates.
  - Invalidation: emit `MsmeEvent` (e.g., `business_updated`) when business data changes; consumers (ICE, cache workers) should subscribe to invalidate/update cache.

- **Subscriptions & payments**:
  - `POST /business/{id}/subscribe_and_pay` may initiate a deposit via `payment-revenue` when `amount_minor` and `phone_number` are provided.
  - MSMe forwards the caller's `Authorization` header to `payment-revenue` for attribution when initiating payment (preserves initiator context).
   - MSMe forwards the caller's `Authorization` header to `payment-revenue` for attribution when initiating payment (preserves initiator context).

  **S2S Workflows & Automation (MSME)**

  - On a successful subscription payment (confirmed by provider callback and recorded by `payment-revenue`), MSME MUST emit an outbox event `msme.subscription.payment_succeeded` containing `business_id`, `subscription_id`, `amount_minor`, `currency`, `occurred_at`, `correlation_id`, and any `affiliate_id`/`affiliate_code` present in context. This event is consumed by `affiliate-engine` for pool funding attribution and may be included in epoch GPR calculations.
  - Emission contract: use OutboxDispatcher; include `event_id` and ensure idempotency (persisted `X-Idempotency-Key`). Do NOT rely on synchronous HTTP POST for this event.
  - Rationale: subscription revenue contributes to Gross Platform Revenue (GPR) for an epoch and must be included when payment-revenue reports `pool_amount` to `affiliate-engine`.

  - The endpoint uses idempotent execution (`idempotent_execute`) keyed by `X-Idempotency-Key` or `event_id` when provided.

- **Event idempotency & recording**:
  - Payment and other important events should be posted with a globally unique `event_id` or `X-Idempotency-Key`.
  - MSME uses `idempotent_execute()` to persist idempotency records (`IdempotencyRecord`) and reject/return cached responses for repeated keys.
  - Endpoints like `/events/payment_success` and `/events/payment_failed` call `idempotent_execute()` internally to ensure deterministic processing.

- **Model example**

```json
{
  "business_id":"biz-555",
  "name":"NTheemba Digital Services",
  "bot_type":"default",
  "fees":{ "platform_percent":5, "affiliate_percent":10 }
}
```

- **Mermaid flow (core interactions)**:

```mermaid
flowchart TD
  ICE -->|GET /business/phone/{phone}| MSME
  MSME -->|returns bot_type & fees| ICE
  Client -->|POST /business/{id}/subscribe_and_pay| MSME
  MSME -->|POST /pawapay/deposits/initiate| Payment-Revenue
  Payment-Revenue -->|callback/event| MSME
  MSME -->|emit MsmeEvent| Outbox
```

- **Plain English Flows**

- **Auth / Service-Token flow**
  - A client logs in or requests a service token via `POST /auth/service-token/{business_id}`. MSME issues a JWT containing `sub`, `role`, and `business_id` (plus `iat`/`exp`). Downstream services validate the signature and use `business_id` + `role` to authorize S2S requests.

- **Business lookup flow**
  - An ingress or service calls `GET /v1/business/phone/{phone}` to resolve the business and `bot_type`. MSME returns the business and owner info; callers should prefer the cache key `businessdetails:{phone}` when available.

- **Subscribe-and-pay flow (simplified)**
  - Caller posts to `POST /business/{id}/subscribe_and_pay` with plan and optional payment fields. If payment is required (`amount_minor`+`phone_number`), MSME calls `payment-revenue` to initiate a deposit, forwarding the caller `Authorization` header for attribution. MSME records the subscription and relies on payment events to finalize state.

- **Payment event handling**
  - Payment-Revenue or other payment providers post to MSME's `/events/payment_success` (or `/events/payment_failed`). MSME uses `idempotent_execute()` keyed by `X-Idempotency-Key`/`event_id` to ensure the event is processed exactly once: it records an `MsmeEvent`, updates subscription/business state, and emits outbox events for downstream consumers.

- **Notification proxy flow**
  - Frontend or services call MSME's notification proxy endpoints; MSME forwards requests to the central notification service with `X-Correlation-Id` and `Authorization` when present. Notification calls are best-effort and do not block core flows.

- **Cache invalidation flow**
  - When business data changes, MSME persists an `MsmeEvent` like `business_updated`. Cache workers or downstream services subscribe to these events and invalidate `businessdetails:{phone}` to refresh stale caches.

- **Operational notes / conventions**:
  - Use long-cache TTL (24h) for `businessdetails:{phone}` and invalidate on `business_updated` MsmeEvents.
  - Require and forward `X-Correlation-Id` on cross-service calls; use it for logging and audit.
  - Require `X-Idempotency-Key` or `event_id` for payment-related endpoints; persist idempotency using `IdempotencyRecord`.
  - Secure S2S calls using bearer tokens; downstream services should validate JWT signature and claims using the shared `get_jwt_secret()`.
  - Tests should cover idempotency, token issuance for `auth/service-token`, and `subscribe_and_pay` flows with forwarded auth.

  - **Background subscription scheduler (current implementation)**
    - MSME includes a background job (`subscription_reminder.py`) that:
      - Sends reminders at 7, 3 and 1 day before subscription expiry.
      - Attempts an automated deposit (auto-pay) at expiry by calling `payment-revenue` (`/pawapay/deposits/initiate`) with a scheduler JWT.
      - Marks `auto_pay_attempted` and, if auto-pay has already been attempted and the subscription is still expired, downgrades the business to the `free` plan and emits a `subscription_downgraded` MsmeEvent.
      - Emits audit events for reminders, auto-pay attempts and downgrades.

  - **How to switch to "send payment link" (non-auto-pay) mode**
    - Recommended approach: introduce a configuration flag (e.g. `SUBSCRIPTION_AUTO_PAY_ENABLED=false`) or per-business `auto_pay_enabled` field.
    - Modify `subscription_reminder.py` logic to:
      - When a reminder action is due, send a payment link (via notification service) instead of attempting auto-pay at expiry.
      - Record link send attempts and retries (3 attempts, 24h apart by default).
      - Only attempt auto-pay if `auto_pay_enabled` is true (for businesses that opted in).
      - Keep the existing idempotency/audit/emitting behavior.
    - This change keeps scheduling, audit and downgrade semantics but removes the automatic deposit step, matching a non-invasive roll-out.


