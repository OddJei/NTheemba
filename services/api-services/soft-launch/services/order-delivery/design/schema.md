# Schema (Soft Launch)

SQLite tables (names shown conceptually):

## orders
- `id` (uuid, pk)
- `session_id` (text, nullable)
- `user_phone` (text, indexed)
- `user_id` (text, nullable)
- `business_id` (text, indexed)
- `status` (text) — `pending_payment` | `paid` | `delivered`
- `delivery_method` (text) — `pickup` | `deliver_to_customer`
- `total_amount` (integer) — cents
- `currency` (text)
- `metadata` (json)
- `created_at` (datetime)
- `updated_at` (datetime)

## deliveries
- `id` (uuid, pk)
- `order_id` (uuid, indexed)
- `user_phone` (text, indexed)
- `user_id` (text, nullable)
- `business_id` (text, indexed)
- `delivery_method` (text)
- `delivery_code_salt` (text)
- `delivery_code_hash` (text, indexed)
- `status` (text) — `pending` | `code_sent` | `confirmed`
- `confirmed_by` (text, nullable)
- `metadata` (json)
- `created_at` (datetime)
- `updated_at` (datetime)

## outbox_events
- `id` (uuid, pk)
- `event_type` (text)
- `payload` (json)
- `processed` (bool)
- `created_at` (datetime)

## idempotency_records
- `id` (uuid, pk)
- `scope` (text)
- `key` (text)
- `status_code` (integer)
- `response_body` (json)
- `created_at` (datetime)

