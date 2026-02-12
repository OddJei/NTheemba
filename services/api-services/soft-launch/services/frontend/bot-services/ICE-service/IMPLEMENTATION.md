# ICE Service Implementation Plan (Backend‑First)

This checklist starts with **backend-facing layers** because the backend stack is stable. Bot-facing contracts are implemented after adapters and state are solid.

---

## Phase 0 — Project Baseline

**Goal:** lock down baseline decisions so backend adapters can proceed without ambiguity.

### 0.1 Ownership + Repo Layout
- [x] Define ICE service ownership and repo layout
	- Owner: ICE Service Team (backend integration)
	- Repo root: `services/frontend/bot-services/ICE-service/`
	- Proposed structure:
		- `app/api/` (FastAPI routes + schemas)
		- `app/orchestration/` (hydrate/reserve/confirm workflows)
		- `app/adapters/` (catalog, cart/order, payment, delivery, affiliate, msme)
		- `app/state/` (postgres + redis repositories)
		- `app/streams/` (ice:preload, ice:hydrated, oob:audit workers)
		- `app/shared/` (errors, idempotency, schema registry)

### 0.2 Runtime Stack
- [x] Confirm runtime stack (FastAPI + async)
	- FastAPI + asyncio for API and workers
	- Postgres JSONB (source of truth)
	- Redis (cache + streams)

### 0.3 Error Codes + Idempotency Rules
- [x] Establish shared error codes and idempotency rules
	- **Error code shape:** `ICE_<DOMAIN>_<REASON>` (e.g., `ICE_RESERVE_OUT_OF_STOCK`)
	- **Client retries:** only on 5xx and `ICE_TEMPORARY_UNAVAILABLE`
	- **Idempotency:** required for reserve/confirm; `idempotency_key = event_id`
	- **Replay:** if `idempotency_key` exists, return stored response

### 0.4 JSONB Schema Registry
- [x] Define JSONB schema registry and versioning policy
	- Every blob includes `schema_version` and `updated_at`
	- Backward compatibility via read-time transforms
	- Registry stored in `app/shared/schema_registry.py`
	- Versions tracked per blob type: `session`, `oob`, `product`, `catalog`, `affiliate_ctx`

---

## Phase 1 — Backend Adapters (Priority)

- [x] Scaffold adapter interfaces + stubs

### 1.0 Bot Session Infrastructure Adapter
- [x] Map endpoints and document API contracts
- [x] Implement health check (GET /health)
- [x] Implement session retrieval (GET /session/{id})
- [x] Implement Redis stream operations (direct Redis client)
- [x] Add unit tests for session CRUD and stream operations
- [x] Use real BOT_SESSION_URL from environment
- [x] Create adapter factory with singleton pattern
- [x] Add integration tests with real service

### 1.0b User-Bot Conversation Session Adapter
- [x] Map endpoints and document API contracts
- [x] Implement session creation (POST /session/create)
- [x] Implement session state retrieval (GET /session/{id})
- [x] Implement session closure (POST /session/{id}/close)
- [x] Implement active sessions query (GET /session/resolve)
- [x] Add unit tests for session lifecycle
- [x] Use real BOT_SESSION_URL from environment
- [x] Create adapter factory with singleton pattern
- [ ] Coordinate with bot-session team for context update endpoint

### 1.0c Authentication Adapter (MSME Engine)
- [x] Create shared auth adapter for user verification
- [x] Implement user verification (GET /auth/phone/{phone})
- [x] Implement business profile retrieval (GET /businesses/{business_id})
- [x] Use real MSME_ENGINE_URL from environment
- [x] Add integration tests
- [x] Create workflow simulation demonstrating all adapters

### 1.1 Catalog/Inventory Adapter
- [ ] Define adapter interface
- [ ] Map backend endpoints for product list + product snapshot
- [ ] Implement inventory availability + price snapshot fetch
- [ ] Add unit tests for out-of-stock and price-change cases

### 1.2 Cart/Order Adapter
- [ ] Define cart draft create/update API mapping
- [ ] Implement reserve inventory call (backend order/cart)
- [ ] Implement order confirmation mapping
- [ ] Add idempotency headers on backend requests

### 1.3 Payment/Revenue Adapter
- [ ] Implement payment intent creation
- [ ] Implement payment status confirmation fetch
- [ ] Map payout ledger update (if required)

### 1.4 Delivery Adapter
- [ ] Implement delivery fee validation
- [ ] Implement delivery code generation hook
- [ ] Implement delivery confirmation mapping

### 1.5 Affiliate Adapter
- [x] Implement attribution logging call
- [x] Implement affiliate context hydration
- [x] Implement commission event emission hook

### 1.6 MSME Adapter
- [x] Implement business profile hydration
- [x] Implement policy/feature flags hydration

---

## Phase 2 — Persistence & Cache Layer

**Status:** ✅ **COMPLETE**

### 2.1 Postgres JSONB Models (13 Blob Types)
- [x] Create SQLAlchemy ORM for all 13 blobs
- [x] Add smart indexing (user_id, business_id, order_id, affiliate_id, etc.)
- [x] Add timestamps (created_at, updated_at, confirmed_at)
- [x] Add status tracking (draft, confirmed, paid, delivered, attributed)
- [x] Add composite keys for time-windowed data (affiliate performance)

### 2.2 Repository Layer (CRUD)
- [x] Implement `IceRepository` class with async save/get for all 13 blobs
- [x] Atomic save-or-update pattern (insert if missing, update if exists)
- [x] Transaction management (commit/rollback)
- [x] Comprehensive logging

### 2.3 Redis Cache Layer
- [x] Add blob-specific cache methods (hydrated session, cart, order, product, etc.)
- [x] TTL strategy (1–60m per blob type based on freshness)
- [x] Single-flight locks (prevent concurrent hydrations)
- [x] Negative caching (skip failed hydrations for 5m)
- [x] Pattern-based deletion support

### 2.4 Hydration Workflow (Phase 3.1)
- [x] Rewrite to compose all 13 blobs from adapters
- [x] Parallel adapter calls (asyncio.gather)
- [x] Atomic persistence to Postgres (source of truth)
- [x] Cache hot blobs in Redis (by TTL)
- [x] Emit `ice:hydrated` event to stream
- [x] Error handling (rollback, negative cache, lock release)

### 2.5 Documentation
- [x] Create JSONB_SCHEMA_REGISTRY.md (complete field mappings, adapter dependencies)
- [x] Create PHASE2-COMPLETE.md (architecture, deployment, TTL strategy)

### 2.6 Test Suite
- [x] Create test_phase2_persistence.py with:
	- Test 1: All 13 CRUD operations
	- Test 2: All cache operations (set/get, locks, negative cache)
	- Test 3: Full hydration workflow
	- Test 4: Two-tier fallback (Redis → Postgres)

---

## Phase 3 — Orchestration Layer

### 3.1 Hydration Workflow
- [x] Compose session blob from adapters
- [x] Parallel adapter calls (bot-session, MSME, catalog, affiliate)
- [x] Compose hydrated session ICE blob
- [x] Write all 13 blobs to Postgres + Redis
- [x] Emit `ice:hydrated` event to stream
- [x] Single-flight locks + negative cache

### 3.2 Reserve Workflow ✅ **COMPLETE**
- [x] Validate cart draft + schema version
- [x] Call inventory/cart/order adapters (parallel)
- [x] Reserve inventory atomically
- [x] Persist reservation result + price snapshot (order_draft blob)
- [x] Cache order draft in Redis (60m TTL)
- [x] Single-flight locks + idempotency
- [x] Negative cache for OUT_OF_STOCK (5m)
- [x] Emit audit event (ice:reserved)

### 3.3 Confirm Workflow ✅ **COMPLETE**
- [x] Validate payment reference
- [x] Confirm order via order adapter (create order + initiate payment)
- [x] Trigger delivery creation (delivery task blob)
- [x] Update affiliate attribution + commission events
- [x] Persist final order state (order_confirmed blob)
- [x] Cache order confirmed in Redis (30–120m TTL)
- [x] Single-flight locks + idempotency
- [x] Error handling (rollback, negative cache)
- [x] Payment status fetch workflow
- [x] Order cancellation workflow

---

## Phase 4 — Bot-Facing API Layer (✅ COMPLETE)

- [x] Implement FastAPI application (`app/main.py`)
- [x] Create API routes module (`app/api/routes.py`)
  - [x] Health check endpoints (GET /health, GET /ready)
  - [x] Hydration endpoint (POST /api/v1/hydrate/session)
  - [x] Reserve endpoint (POST /api/v1/reserve)
  - [x] Confirm endpoint (POST /api/v1/confirm)
  - [x] Payment status endpoint (GET /api/v1/orders/{order_id}/payment_status)
  - [x] Cancel endpoint (POST /api/v1/orders/{order_id}/cancel)
- [x] Create Pydantic schemas (`app/api/schemas.py`)
  - [x] Request models with validation
  - [x] Response models with JSON examples
  - [x] Error response models
- [x] Add request validation + error mapping
- [x] Add idempotency key support (2h for reserve, 4h for confirm, 1h for hydrate)
- [x] Add global error handler
- [x] Dependency injection (db, redis)
- [x] Lifespan management (startup/shutdown)
- [x] OpenAPI documentation (Swagger + ReDoc)
- [x] Database session dependency (get_db)

---

## Phase 5 — Async Streams & Workers ✅ **COMPLETE**

### 5.1 Ice:Preload Consumer Worker
- [x] Consume `ice:preload` stream (async hydration requests)
- [x] Run HydrationWorkflow in background (non-blocking)
- [x] Cache hydrated blobs (session, order_draft, bot_meta) in Redis (10m TTL)
- [x] Publish results to `ice:hydrated` stream
- [x] Error handling: retry up to MAX_ATTEMPTS (default 2)
- [x] DLQ handling: push failed requests to `ice:preload:dlq`
- [x] Consumer group management (XREADGROUP + XAUTOCLAIM)

### 5.2 OOB Audit Writer Worker
- [x] Consume `oob:audit` stream (Order Object mutation events)
- [x] Persist events to PostgreSQL `oob_audit` table (append-only)
- [x] Parse oob_patch and extract event type (cart_mutation, payment_mutation, etc.)
- [x] Include metadata: event_id, session_id, order_id, intent_ids, result
- [x] Error handling: retry up to MAX_ATTEMPTS (default 3)
- [x] DLQ handling: push failed entries to `oob:audit:dlq`
- [x] Consumer group management (XREADGROUP + XAUTOCLAIM)

### 5.3 Async Workers Integration
- [x] Register workers in FastAPI lifespan (startup/shutdown)
- [x] Graceful shutdown on SIGTERM (asyncio.CancelledError)
- [x] Logging: structured logs with event context
- [x] Configuration via environment variables (stream names, TTL, max attempts)

### 5.4 Future Work (Not Implemented)
- [ ] TTL cleanup job for stale sessions (expire old cache keys)
- [ ] Cache refresh job for hot products (background refresh)
- [ ] Stream compaction (XTRIM for large streams)

---

## Phase 6 — Observability & Ops ✅ **COMPLETE**

### 6.1 Structured Logging
- [x] Configure JSON logging formatter (for ELK/CloudWatch)
- [x] Structured LogContext class with context fields
- [x] Recommended context fields: event_id, session_id, order_id, user_id, bot_id, correlation_id, duration_ms, status, error_code
- [x] Exception logging with type + message
- [x] Logger setup function for modules

### 6.2 Prometheus Metrics
- [x] API endpoint latencies (hydrate, reserve, confirm, payment_status, cancel)
- [x] Request counts with status labels (success, validation_error, server_error)
- [x] Workflow latencies (hydration, reservation, confirmation)
- [x] Workflow errors by type and error code
- [x] Cache metrics: hits, misses, size by cache_type
- [x] Database metrics: query latency, errors, connection pool size
- [x] Stream metrics: messages processed, processing latency, lag, dlq count
- [x] Business metrics: orders created/confirmed/cancelled, payments by method, cart value
- [x] Track decorator for automatic latency measurement

### 6.3 Health & Readiness Checks
- [x] HealthChecker class: checks Redis, Database, Streams
- [x] ReadinessChecker class: checks if service ready for requests
- [x] Health check results: status enum (healthy, degraded, unhealthy)
- [x] Component-level health: Redis memory, DB connections, stream consumer groups
- [x] Ready signal: both Redis and DB must be accessible

### 6.4 Load Testing Suite
- [x] Locust-based load tests with multiple user profiles
- [x] ICEServiceUser: balanced workload (hydrate, reserve, confirm, payment_status, cancel)
- [x] ConcurrentReserveUser: stress test (concurrent rapid requests)
- [x] IdempotencyTestUser: verify idempotency (same request twice returns same result)
- [x] Test data generators: event_id, session_id, order_id, phone
- [x] Event listeners: test start/stop with summary statistics
- [x] Test scenarios: 100 users 5m, 500 users 10m, etc.
- [x] Expected results: P95 <500ms, P99 <1000ms, error rate <1%

### 6.5 OpenAPI/Swagger Documentation
- [x] All endpoints documented with descriptions + examples
- [x] Request/response schemas visible in Swagger UI
- [x] Error codes documented (ICE_RESERVE_OUT_OF_STOCK, etc.)
- [x] Idempotency strategy documented
- [x] Available at `/docs` (Swagger) and `/redoc` (ReDoc)

---

## Phase 7 — Contract Validation (Bot Layer)

- [x] Validate JSONB shapes vs bot docs
- [x] Simulate bot session end-to-end
- [x] Verify Redis keys + TTL behavior
- [x] Compatibility tests for schema migrations

---

## Deliverables Summary

- Backend adapters stable and tested
- JSONB persistence + Redis cache operational
- Orchestration workflows deterministic
- Bot-facing API implemented after backend stability
- Streams + audit in place
- Observability + load testing

---

## Status Tracking

- Owner: ICE Service Team
- Start: 2026-02-04
- Target: TBD
