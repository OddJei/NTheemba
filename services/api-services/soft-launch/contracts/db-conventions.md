# Soft Launch DB Conventions (Harmonized)

Applies to: cart, order, affiliate-engine, msme-engine, bot-session, payment-revenue, notification, delivery.

## 1) IDs and shared fields
- All primary keys: UUID (id)
- Foreign keys should use consistent names:
  - business_id (preferred) for MSME/business ownership
  - user_id (nullable) and user_phone (nullable) for identity
  - session_id for bot context
  - order_id/cart_id/payment_id/delivery_id where applicable
- Standard audit fields on all tables:
  - created_at (TIMESTAMP)
  - updated_at (TIMESTAMP)
- Use metadata JSONB when you need flexibility (avoid schema drift).

## 2) Phone-first identity (soft launch)
- user_phone is the primary identifier for anonymous flows.
- user_id is optional (set when Auth resolves a user).

## 3) Status fields
- Prefer ENUMs or constrained TEXT values.
- Dont invent new status words per service; use the status-mapping doc for canonical meanings.

## 4) Idempotency
- Any endpoint triggered by external gateways or bots should accept:
  - idempotency_key (TEXT) and enforce uniqueness for safe retries.
- Payment verification callbacks MUST be idempotent.

## 5) Outbox (recommended)
For automated workflows, each service that emits events should have an outbox table:
- outbox_events(id, aggregate_type, aggregate_id, event_type, payload_json, status, created_at, published_at)
This prevents "DB commit succeeded but event publish failed".
