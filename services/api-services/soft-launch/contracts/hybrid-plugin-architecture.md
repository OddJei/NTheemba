# Hybrid Plugin Architecture (Soft Launch)

You chose the **hybrid approach**:

1) **Service-based adapters (thin)**
- One adapter per backend service (Cart/Order/Payment/Delivery/Notification/Affiliate/MSME).
- Adapters wrap raw HTTP calls via the shared `AsyncServiceClient` transport plugin system.
- These are stable, reusable building blocks.

2) **Automation-based plugins (composed)**
- One automation plugin per end-to-end workflow step.
- Automation plugins call multiple adapters to complete a business workflow.
- This keeps the bot contract simple: **one call per automation step**.

3) **ICE (orchestrator/router)**
- ICE routes bot requests to the correct automation plugin.
- ICE does NOT embed raw HTTP logic; it only composes automation plugins.

## Why this is best for the soft launch

- Soft-launch simplicity: bot integration stays stable (few operations).
- Future scalability: adapters remain reusable even if workflows change.
- Auditability: one place to apply correlation/idempotency/retry/auth (middleware).

## Layering

Business modules
→ Automation Plugins (workflow)
→ Service Adapters (per service)
→ AsyncServiceClient (operation_map)
→ Middleware chain (correlation/idempotency/auth/retry/observability)
→ Transport (HttpxAsyncTransport | MockTransport)

## Recommended soft-launch automation plugins

- `OrderCreationPlugin`
  - Input: user + business + items + delivery details (+ affiliate_code optional)
  - Steps: create cart → add items → checkout → create order
  - Output: order_id + totals + status

- `PaymentFlowPlugin`
  - Input: order_id + amount + payer (user_phone)
  - Steps: initiate payment → verify/confirm → emit `payment_success`/`payment_failed`
  - Output: payment_id + status

- `DeliveryPlugin`
  - Input: order_id + business_id
  - Steps: generate delivery code → confirm code → mark delivered → trigger payout_ready
  - Output: delivery_id + status

- `NotifyPlugin`
  - Input: template + recipients + payload
  - Steps: send message(s)

## Standard cross-cutting rules

- Every automation call MUST accept/pass:
  - `correlation_id`
  - `idempotency_key` (for retryable POST/PUT steps)
- Automation plugins should treat downstream calls as **idempotent** where possible.

## Where the reference code lives

- Transport + middleware + operation map:
  - `api-services/soft-launch/contracts/python/soft_launch_client/`

If you want, we can add a thin `ice/` module inside each runnable service to standardize how plugins are registered and invoked.
