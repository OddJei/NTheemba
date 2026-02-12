# Phase 2 Complete: Persistence Layer (Postgres JSONB + Redis Cache)

**Date:** February 4, 2026  
**Status:** ✅ COMPLETE

## What Was Implemented

### 1. Postgres Models (13 JSONB Blob Types)

File: `app/state/models.py`

All 13 blob types now have SQLAlchemy ORM models:

| Blob | Table | Purpose |
|------|-------|---------|
| 1 | `ice_bot_core` | Bot control plane + live stats |
| 2 | `ice_owner_profile` | Owner identity + business profile (MSME) |
| 3 | `ice_catalog_index` | Product list for business |
| 4 | `ice_product_snapshot` | Individual product with inventory |
| 5 | `ice_session_snapshot` | User session state |
| 6 | `ice_hydrated_session` | Hydrated session context (ICE) |
| 7 | `ice_cart` | Shopping cart (pre-checkout) |
| 8 | `ice_order_draft` | Order draft (pre-checkout) |
| 9 | `ice_order_confirmed` | Confirmed order (post-checkout) |
| 10 | `ice_delivery_task` | Delivery task |
| 11 | `ice_affiliate_session_context` | Affiliate tracking in session |
| 12 | `ice_order_attribution` | Order → affiliate attribution |
| 13 | `ice_affiliate_performance` | Affiliate metrics summary |

**Features:**
- ✓ JSONB `blob` column for each table
- ✓ Smart indexing on frequently-queried fields (user_id, business_id, order_id, etc.)
- ✓ Automatic `created_at` / `updated_at` timestamps
- ✓ Status tracking for orders, deliveries, attributions
- ✓ Composite keys for time-windowed data (affiliate performance by date range)

### 2. Repository Layer (CRUD Operations)

File: `app/state/repository.py`

Complete CRUD operations for all 13 blob types:

```python
# Example method signatures:
await repo.save_hydrated_session(session_id, user_id, business_id, blob)
await repo.get_hydrated_session(session_id)

await repo.save_cart(cart_id, user_id, business_id, blob)
await repo.get_cart(cart_id)

await repo.save_order_confirmed(order_id, user_id, business_id, blob, status, confirmed_at)
await repo.get_order_confirmed(order_id)

# etc. for all 13 types
```

**Features:**
- ✓ Atomic save-or-update pattern (insert if missing, update if exists)
- ✓ Automatic timestamp management
- ✓ Transaction management (commit/rollback)
- ✓ Logging for all operations
- ✓ Async/await for all I/O

### 3. Redis Cache Layer

File: `app/cache/redis_client.py` (enhanced)

New blob-specific cache methods added:

```python
# Phase 2 blob cache methods:
await redis.set_hydrated_session(session_id, data, ttl_minutes=30)
await redis.get_hydrated_session(session_id)

await redis.set_product_snapshot(product_id, data, ttl_minutes=10)
await redis.get_product_snapshot(product_id)

await redis.set_cart(cart_id, data, ttl_minutes=30)
await redis.get_cart(cart_id)

await redis.set_order_draft(order_id, data, ttl_minutes=60)
await redis.get_order_draft(order_id)

# Single-flight locks (prevent concurrent hydrations):
await redis.set_hydrate_lock(session_id, ttl_seconds=30)
await redis.release_hydrate_lock(session_id)

# Negative caching (skip failed hydrations):
await redis.set_negative_hydrate_cache(session_id, ttl_minutes=5)
await redis.get_negative_hydrate_cache(session_id)

# Flexible deletion:
await redis.delete("cache:session:*")  # Pattern delete
await redis.delete("cache:hydrated:sess-123")  # Exact delete
```

**Features:**
- ✓ Per-blob-type TTLs (1–60 minutes based on data freshness)
- ✓ Single-flight locks (prevent concurrent hydrations of same session)
- ✓ Negative cache (avoid retrying failed hydrations for 5m)
- ✓ Pattern-based deletion (useful for cleanup)
- ✓ Async/await for all operations
- ✓ Comprehensive logging

### 4. Hydration Workflow (Phase 3.1)

File: `app/orchestration/hydrate.py` (completely rewritten)

Full session hydration now handles all 13 blobs:

```python
workflow = HydrationWorkflow(db, redis)
ice_blob = await workflow.hydrate_session(
    session_id="sess:123",
    user_id="user:456",
    bot_id="bot:test",
    business_id="BIZ-001",
    phone_number="260701234567",
    affiliate_code="aff-code-123",  # Optional
    correlation_id="corr:789",  # Tracing
)
```

**Steps:**
1. ✓ Acquire single-flight lock (prevent concurrent hydrations)
2. ✓ Check negative cache (skip recent failures)
3. ✓ Fetch context from all 8 adapters in **parallel**:
   - Bot-session (session snapshot)
   - MSME (owner profile, business policies)
   - Catalog/Inventory (catalog index)
   - Affiliate (affiliate context)
4. ✓ Compose hydrated session ICE blob (main blob with all context)
5. ✓ Persist atomically to Postgres (source of truth):
   - Ice hydrated session (6)
   - Owner profile (2)
   - Catalog index (3)
   - Affiliate session context (11)
   - Session snapshot (5)
6. ✓ Cache hot blobs in Redis (by TTL):
   - Hydrated session (30m)
   - Catalog (5–10m, already cached)
   - Affiliate context (24h)
7. ✓ Emit `ice:hydrated` event to Redis stream
8. ✓ Release lock + handle failures gracefully

**Error Handling:**
- ✓ Rollback on adapter failures (doesn't persist partial state)
- ✓ Negative cache prevents retry storms
- ✓ Lock prevents concurrent hydrations
- ✓ Comprehensive logging for debugging

### 5. Test Suite

File: `scripts/test_phase2_persistence.py`

Complete test coverage:

```bash
python -m scripts.test_phase2_persistence
```

**Tests:**
1. ✓ Postgres models: Save/retrieve all 13 blob types
2. ✓ Repository CRUD: Full lifecycle for each blob
3. ✓ Redis cache: Set/get, TTLs, locks, negative cache
4. ✓ Hydration workflow: Full orchestration flow

## Architecture

### Two-Tier Caching Strategy

```
┌─────────────────────────────┐
│   User Request (Session)    │
└──────────┬──────────────────┘
           │
           v
┌─────────────────────────────┐
│   1. Check Redis (Hot)      │◄──── Cache hit (1–30m TTL)
│   (async, <5ms)             │
└──────────┬──────────────────┘
           │ Miss
           v
┌─────────────────────────────┐
│   2. Check Postgres (Cold)  │◄──── DB hit, refresh Redis
│   (async, <50ms)            │
└──────────┬──────────────────┘
           │ Miss
           v
┌─────────────────────────────┐
│   3. Hydrate from Adapters  │◄──── Run workflow
│   (async, parallel, ~1s)    │      Compose + Persist
└──────────┬──────────────────┘
           │
           v
┌─────────────────────────────┐
│   4. Persist & Cache        │
│   - Postgres (source)       │
│   - Redis (hot layer)       │
│   - Emit event              │
└─────────────────────────────┘
```

### Data Flow

```
Adapters (8)
├─ Bot-session  ─→ Session snapshot (5)
├─ MSME        ─→ Owner profile (2)
├─ Catalog      ─→ Catalog index (3) + Product snapshots (4)
├─ Cart-Order   ─→ Cart (7), Order draft (8), Order confirmed (9)
├─ Payment      ─→ Order payment fields
├─ Delivery     ─→ Delivery task (10)
├─ Affiliate    ─→ Affiliate context (11) + Attribution (12)
└─ Affiliate    ─→ Performance summary (13)
         │
         v
Hydrate Workflow
         │
         v
ICE Blob (6) ← Main hydrated session context
         │
         v
Postgres (Source of Truth)
├─ ice_hydrated_session
├─ ice_owner_profile
├─ ice_catalog_index
├─ ice_session_snapshot
├─ ice_affiliate_session_context
└─ (10 more tables for orders, carts, etc.)
         │
         v
Redis (Hot Cache)
├─ cache:hydrated:session-id (30m)
├─ cache:catalog:business-id (5m)
├─ cache:product:product-id (10m)
├─ cache:cart:cart-id (30m)
└─ cache:order:draft:order-id (60m)
```

## TTL Strategy

| Blob Type | Redis TTL | Rationale |
|-----------|-----------|-----------|
| Hydrated session (6) | 30m | User session activity |
| Catalog index (3) | 5–10m | Infrequent product updates |
| Product snapshot (4) | 1–10m | Real-time inventory |
| Cart (7) | 30m | User session activity |
| Order draft (8) | 60m | Shopping session |
| Session snapshot (5) | 30m | User session activity |
| Affiliate context (11) | 24h | Stable tracking info |
| Owner profile (2) | 6–24h | Business profile stability |
| Bot core (1) | 5–30m | Live stats |
| Order confirmed (9) | 30–120m | Immutable post-checkout |
| Delivery task (10) | 30–180m | Multi-hour fulfillment |
| Attribution (12) | 30–120m | Post-order metrics |
| Performance (13) | 5–60m | Dashboard cache |

## Deployment

### Database Setup

```bash
# Postgres migrations (handled by SQLAlchemy):
from app.state.models import Base, engine
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
```

### Required Services

```yaml
# docker-compose.yml updates needed:
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: ice_service
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

### Environment Variables

```bash
# .env.docker / .env.local
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/ice_service
REDIS_URL=redis://localhost:6379/0
```

## What's Next (Phase 3.2+)

- [ ] Phase 3.2: Reservation workflow (reserve inventory atomically)
- [ ] Phase 3.3: Order confirmation workflow (payment → order → delivery chain)
- [ ] Phase 4: Bot-facing API endpoints (FastAPI routes for hydration, cart, order)
- [ ] Phase 5: Async workers (process background jobs, retry failed operations)

## Summary

✅ **Phase 2 Complete:**
- 13 JSONB blob types modeled in Postgres
- Full CRUD repository layer (async-safe)
- Redis cache layer with smart TTLs
- Hydration workflow orchestrating all adapters
- Single-flight locks + negative caching
- Atomic persistence + two-tier caching
- Comprehensive test suite

**Status:** Ready for Phase 3.2 (Reservation workflow) and Phase 4 (API endpoints)
