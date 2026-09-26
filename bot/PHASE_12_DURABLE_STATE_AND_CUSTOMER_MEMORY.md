# Phase 12 — Durable Runtime State and Customer Memory

Phase 12 moves Ntheemba from process-local state to a hybrid persistence model:

- **Redis** owns state needed while a conversation is active.
- **PostgreSQL** owns durable customer identity, consent and business-private memory.
- **TradeFlow** remains the operational system of record for orders, bookings and business activity.
- **NCPC** remains the shared product-identity layer.

The default backends remain `memory` so the application and automated tests can run without external services. Production-style persistence is enabled explicitly through environment variables.

## Architecture

```text
WhatsApp / Developer Simulator
            │
            ▼
      NtheembaService
            │
      ┌─────┴───────────┐
      │                 │
      ▼                 ▼
Redis runtime       PostgreSQL memory
- active session    - platform customer
- session archive   - business relationship
- conversation lock - consent decisions
- message dedupe    - permitted names/addresses
- idempotency       - question analytics
                    - conversation summaries
```

The customer-memory path is **fail-open** during message processing. A temporary PostgreSQL failure is audited and traced, but it does not prevent the customer from receiving the normal workflow reply.

## Phase breakdown

### 12.1 Redis foundation

- asynchronous Redis lifecycle;
- explicit close on application shutdown;
- environment-separated, encoded key namespaces;
- health/readiness checks;
- lazy dependency loading so memory-only tests remain dependency-free.

### 12.2 PostgreSQL foundation

- asynchronous Psycopg connection pool;
- ordered SQL migrations;
- tenant-aware repository scopes;
- health/readiness checks;
- PostgreSQL 16 local Docker service.

### 12.3 Durable customer identity and consent

- conservative E.164 phone normalization with Zambia `+260` default;
- platform customer identity;
- one private business relationship per customer/business pair;
- business-preferred names;
- explicit consent records for cross-business recognition, saved platform checkout details, message retention and marketing.

### 12.4 Durable session repository

- versioned, allow-listed JSON serialization;
- optimistic Redis revisions using `WATCH`/`MULTI`;
- configurable active-session TTL;
- session archive TTL;
- conflict detection rather than silent overwrite.

### 12.5 Cross-business recognition and checkout reuse

A customer can be recognised by normalized phone number across participating businesses only when `cross_business_recognition` consent is granted.

Permitted platform details can then be reused at another business. Business-private names, addresses, questions, orders, bookings and notes are never exposed to a different business.

The real order and booking workflows receive a privacy-filtered customer context. They may reuse:

- a permitted customer name;
- the normalized WhatsApp phone number;
- the current business's saved delivery location;
- a platform delivery location only when saved-checkout consent is granted.

When enough information is available, the workflow moves directly to review instead of asking the customer to type the same checkout details again.

### 12.6 Customer memory and question analytics

- business-private preferred names are learned from completed order/booking details;
- business-specific delivery locations are retained for faster repeat checkout;
- information and FAQ questions are classified as answered, partial or unresolved;
- terminal order, booking and handover outcomes create compact summaries;
- raw message retention requires separate `conversation_retention` consent;
- protected developer diagnostics can inspect one business/customer memory view.

### 12.7 Locking, deduplication and idempotency

- ownership-safe Redis conversation locks;
- periodic lock renewal;
- lock timeout and lock-loss detection;
- atomic message-ID claims with TTL;
- owner-token external-action idempotency records;
- safe complete, fail and release operations.

The idempotency store is available for live gateway/TradeFlow adapters. Existing order and booking workflows continue sending stable idempotency keys to TradeFlow.

### 12.8 Privacy, row security and retention

PostgreSQL migrations include row-level security for business-private tables. Repository transactions set `app.business_id` and `app.customer_id` before accessing scoped rows.

Retention helpers remove expired:

- conversation messages;
- conversation summaries;
- customer questions.

Production deployments should connect with a dedicated non-superuser application role. PostgreSQL superusers bypass row-level security and must not be used by the application.

### 12.9 Developer simulator and diagnostics

The Phase 11.11 chat simulator uses the configured session, lock and deduplication adapters. With Redis enabled, the simulated conversation survives an application restart.

Customer-memory endpoints are available only through the protected developer surface:

```text
GET  /dev/storage
POST /dev/storage/self-check
POST /dev/storage/customers/recognize
POST /dev/storage/customers/name
POST /dev/storage/customers/consent
POST /dev/storage/customers/address
POST /dev/storage/customers/checkout-context
GET  /dev/storage/customers/memory
```

### 12.10 Operational readiness

- Docker Compose for Redis and PostgreSQL;
- PostgreSQL migration runner;
- retention cleanup command;
- storage self-check command;
- readiness integration;
- memory backends for unit tests and local fallback;
- production configuration validation.

## Local durable-state setup

### 1. Start Redis and PostgreSQL

```powershell
docker compose -f docker-compose.phase12.yml up -d
```

Check the containers:

```powershell
docker compose -f docker-compose.phase12.yml ps
```

### 2. Install dependencies

```powershell
python -m pip install -e ".[dev]"
```

### 3. Apply PostgreSQL migrations

```powershell
python scripts\migrate_postgres.py `
  --dsn "postgresql://ntheemba:ladybug101@localhost:5433/ntheembadb"
```

### 4. Enable durable backends

In `.env`:

```env
NTHEEMBA_SESSION_BACKEND=redis
NTHEEMBA_CUSTOMER_BACKEND=postgres
NTHEEMBA_REDIS_URL=redis://localhost:6379/0
NTHEEMBA_POSTGRES_DSN=postgresql://ntheemba:ladybug101@localhost:5433/ntheembadb
```

### 5. Validate storage

```powershell
python scripts\validate_storage.py
```

Expected result:

```text
Storage self-check passed
```

### 6. Start Ntheemba

```powershell
python -m uvicorn ntheemba.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/dev/simulator
http://127.0.0.1:8000/dev/storage
http://127.0.0.1:8000/ready
```

## Manual restart test

1. Start an order in `/dev/simulator`.
2. Stop Uvicorn without deleting Redis data.
3. Start Uvicorn again.
4. Use the same business ID and customer phone.
5. Send the next expected answer.
6. Confirm the workflow resumes from the stored stage.
7. Replay a previously processed message ID and confirm it is treated as a duplicate.

## Customer-recognition test

1. Save a business-private name and address using `/dev/storage/customers/name` and `/dev/storage/customers/address`.
2. Start a delivery order for the same phone number.
3. Confirm Ntheemba reuses the current business's name/address and moves directly to order review.
4. Grant `cross_business_recognition` and `saved_checkout_details` consent.
5. Save a platform-scoped address.
6. Message a second business using the same phone number.
7. Confirm only the consented platform fields are available; the first business's private history remains absent.

## Retention cleanup

```powershell
python scripts\cleanup_customer_memory.py `
  --dsn "postgresql://ntheemba:ladybug101@localhost:5433/ntheembadb" `
  --message-days 90 `
  --summary-days 730 `
  --question-days 730
```

Schedule this command through the deployment platform's job scheduler rather than running it inside every API instance.

## Quality gate

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy ntheemba tests
python scripts\validate_observability.py
python scripts\validate_storage.py
```

The storage self-check requires Redis/PostgreSQL only when those backends are selected.

## Important limitations and next boundary

Phase 12 provides the durable stores and connects customer memory to the real application pipeline and simulator. It does not yet provide the production WhatsApp gateway or live TradeFlow/NCPC HTTP adapters. Those adapters should consume the Redis idempotency store and the existing ports in later integration phases.
