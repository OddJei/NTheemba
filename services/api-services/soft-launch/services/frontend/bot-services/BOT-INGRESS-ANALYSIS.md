# Bot Ingress Service — Architecture & Integration Analysis

**Status:** Inspected February 4, 2026  
**Service Location:** `services/frontend/bot-services/bot-ingress-service/`

---

## Overview

The Bot Ingress Service is the **entry point** for all inbound messages from external channels (SMS, WhatsApp, HTTP callbacks). It:

1. **Validates** inbound payloads for required fields
2. **Enriches** payloads with bot, user, and session context (cache-first approach)
3. **Publishes** enriched envelopes to Redis streams for downstream bot workers
4. **Integrates with ICE** for optional session context preloading

### Key Design Principle: **Cache-First**

Ingress prioritizes Redis cache lookups over HTTP calls to upstream services. This keeps enrichment fast and deterministic. On cache miss, it calls upstream services (Bot/Auth/Capability).

---

## Architecture

```
┌─────────────────────────────────────┐
│  External Channels                  │
│  (SMS, WhatsApp, HTTP)              │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Bot Ingress Service                │
│  ├─ app/main.py                     │
│  │  └─ FastAPI + background listener│
│  │                                  │
│  ├─ workers/queue_listener.py       │
│  │  └─ Async Redis stream consumer  │
│  │                                  │
│  ├─ ingress/                        │
│  │  ├─ validator.py (validate + idempotency)
│  │  ├─ enricher.py (bot/user/capability/session)
│  │  ├─ publisher.py (publish to lanes + audit)
│  │  └─ attachment_builder.py        │
│  │                                  │
│  ├─ clients/                        │
│  │  ├─ bot_service.py               │
│  │  ├─ auth_service.py              │
│  │  ├─ capability_service.py        │
│  │  └─ ice_service.py (ICE integration) │
│  │                                  │
│  └─ services/                       │
│     ├─ cache.py                     │
│     └─ session_manager.py           │
└──────────┬──────────────────────────┘
           │
     ┌─────┴──────┬──────────┬────────────┐
     ▼            ▼          ▼            ▼
  Redis KV      Redis KV    Redis Stream Redis Stream
  (Cache)       (Session)   (bot:lane:*) (ingress:resolved_payload)
                  (Audit)
```

---

## Core Flow (enrich_inbound)

### Step 1: Bot Lookup (Cache-First)

```python
# 1. Check Redis cache for bot info
bot_cache_key = cache_key_bot(inbound.to)
bot_info = await cache.get_json(bot_cache_key)

# 2. On cache miss, call HTTP (if fallback enabled)
if bot_info is None:
    bot_info = await bot_service.get_bot_by_phone(http_client, settings, inbound.to)
    # Cache for next time
    await cache.set_json(bot_cache_key, bot_info, ttl_seconds=settings.bot_cache_ttl_seconds)

# 3. Extract bot type
bot_type = bot_info.get("bot_type", "default")  # "default" or "custom"
```

**Cache Key:** `cache:bot:{phone}`  
**TTL:** `INGRESS_BOT_CACHE_TTL` (default 3600s)

### Step 2: User Lookup (Cache-First, For Custom Bots Only)

```python
if bot_type == "custom":
    business_id = business_details.get("id")
    user_cache_key = cache_key_user(inbound.from_, business_id)
    user_info = await cache.get_json(user_cache_key)
    
    if user_info is None:
        user_info = await auth_service.lookup_user(http_client, settings, inbound.from_, business_id)
        await cache.set_json(user_cache_key, user_info, ttl_seconds=settings.user_cache_ttl_seconds)
```

**Cache Key:** `cache:user:{phone}:{business_id}`  
**TTL:** `INGRESS_USER_CACHE_TTL` (default 900s)

### Step 3: Capabilities Lookup

```python
capabilities_cache_key = cache_key_capabilities(session_mode)
capabilities = await cache.get_json(capabilities_cache_key)

if capabilities is None:
    capabilities = await capability_service.get_capabilities(http_client, settings, session_mode)
    await cache.set_json(capabilities_cache_key, capabilities, ttl_seconds=settings.capabilities_cache_ttl_seconds)
```

**Cache Key:** `cache:capabilities:{mode}`  
**TTL:** `INGRESS_CAPABILITIES_CACHE_TTL` (default 3600s)

### Step 4: Session Context (Optional ICE Preload)

```python
if settings.ice_service_url and settings.ingress_hydrate_first:
    try:
        # Ask ICE to preload session context
        await ice_service.preload_session_context(
            http_client,
            settings,
            event_id=inbound.request_id,
            session_id=session_id,
            user_phone=inbound.from_,
            bot_id=inbound.to,
            platform=inbound.meta.platform,
            bot_type=bot_type,
            required_blobs=["session", "order_draft", "bot_meta"],
        )
    except Exception:
        LOG.debug("ICE preload failed, continuing with cache-only")

# Then check Redis for cached session context
session_context_cache_key = cache_key_session_context(session_id)
session_context = await cache.get_json(session_context_cache_key)
```

**Cache Key:** `cache:session_context:{session_id}`  
**TTL:** `INGRESS_SESSION_CONTEXT_TTL` (default 1800s)

---

## Queue Listener Flow (start_listener)

```
┌─────────────────────────────────┐
│ Redis Stream: ingress:incoming  │  ← Normalized inbound messages
└────────────────┬────────────────┘
                 │ XREAD (blocking)
                 ▼
        ┌─────────────────────┐
        │ Validate + Check    │ ← validate_and_check()
        │ (idempotency check) │
        └────────┬────────────┘
                 │
            Yes  │  No
                 ▼
        ┌─────────────────────┐
    ┌──→│ Enrich Inbound      │ ← enrich_inbound()
    │   │ (bot/user/cap/sess) │
    │   └────────┬────────────┘
    │            │
    │            ▼
    │   ┌─────────────────────┐
    │   │ Publish Enriched    │ ← publish_enriched()
    │   │ ├─ bot:lane:*       │
    │   │ └─ ingress:resolved │
    │   └─────────────────────┘
    │
    └─ (Skip if duplicate)
```

**Processing Steps:**

1. **Read from stream** (`ingress:incoming`) with blocking read
2. **Validate** payload + check idempotency (skip if duplicate)
3. **Enrich** with bot/user/capabilities/session context
4. **Publish** to `bot:lane:{bot_type}` and `ingress:resolved_payload`
5. **Metrics** (observe_processed, observe_dlq)
6. **Error handling** → push to `ingress:dlq` on failure

---

## ICE Service Integration

### Preload Endpoint Called

```
POST /api/v1/hydrate/session
Content-Type: application/json

{
  "event_id": "evt_20251226_0001",
  "session_id": "sess_abc123",
  "user_phone": "260970000001",
  "bot_id": "bot_456",
  "platform": "whatsapp",
  "bot_type": "custom",
  "business_id": "biz_321",
  "reason": "ingress_cache_miss",
  "required_blobs": ["session", "order_draft", "bot_meta"]
}
```

### Configuration

**Environment Variables:**

```bash
# Enable/disable ICE integration
ICE_SERVICE_URL=http://localhost:8000  # (empty = disabled)
ICE_PRELOAD_PATH=/api/v1/hydrate/session

# Enable hydrate-first mode (preload before cache lookup)
INGRESS_HYDRATE_FIRST=false  # (default: disabled for fast path)
```

### When Ingress Calls ICE

1. **Hydrate-First Mode** (if `INGRESS_HYDRATE_FIRST=true`):
   - Ingress calls ICE immediately on new session detection
   - ICE returns session blob for caching in Redis
   - Faster subsequent lookups

2. **Cache-First Mode** (if `INGRESS_HYDRATE_FIRST=false` - default):
   - Ingress tries Redis cache first
   - Only calls ICE on cache miss
   - Optimal for high-volume scenarios

---

## Stream Publishing

### Outputs (From Publisher)

Ingress publishes to **two Redis streams**:

1. **`bot:lane:{bot_type}`** (Primary)
   ```
   bot:lane:default  ← Default bot messages
   bot:lane:custom   ← Custom bot messages
   ```
   Message: EnrichedPayload with routing hints

2. **`ingress:resolved_payload`** (Audit)
   ```
   Canonical resolved envelope for replay/audit
   Persisted for 24-48 hours (TTL configurable)
   ```

3. **`ingress:dlq`** (Dead-Letter Queue - on errors)
   ```
   Failed payloads with error + attempts metadata
   ```

---

## Cache Strategy

### Redis KV Cache Keys

| Key Pattern | TTL | Purpose | Updated By |
|---|---:|---|---|
| `cache:bot:{phone}` | 3600s | Bot metadata | Bot Service HTTP call |
| `cache:user:{phone}:{business_id}` | 900s | User profile | Auth Service HTTP call |
| `cache:capabilities:{mode}` | 3600s | Allowed actions | Capability Service HTTP call |
| `cache:session_context:{session_id}` | 1800s | Session state | ICE Service HTTP call |

### Write Controls

**`REDIS_KV_READ_ONLY`** (env var, default `False`)
- When `True`: No cache writes (KV only), but still publishes to streams
- Useful for read-only deployments or testing

**`REDIS_STREAM_PUBLISH_ENABLED`** (env var, default `True`)
- When `False`: No stream publishing (cache lookups only)
- Useful for cache-warming without affecting consumers

---

## Enriched Payload Structure

### EnrichedPayload (Published to bot:lane:*)

```python
{
  "event_id": "evt_20251226_0001",
  "session_id": "sess_abc123",
  "user_id": "user_789",
  "bot_id": "bot_456",
  "bot_type": "custom",
  "inbound": {
    "from_": "260970000001",
    "to": "+260970000002",
    "message_body": "show me products",
    "request_id": "req_20251226_0001",
    "meta": {
      "platform": "whatsapp",
      "timestamp": "2025-12-26T09:12:00Z"
    }
  },
  "enriched": {
    "bot_meta": {
      "bot_id": "bot_456",
      "business_id": "biz_321",
      "business_name": "Kitwe Solar",
      "default_locale": "en",
      "supported_payment_methods": ["mobile_money", "cash"]
    },
    "user": {
      "user_id": "user_789",
      "phone_masked": "260970*****",
      "name": "John",
      "is_authenticated": true,
      "roles": ["customer"]
    },
    "session": {
      "session_id": "sess_abc123",
      "current_node": "start",
      "expected_input": "text",
      "intent_required": true
    },
    "order_draft": {
      "status": "building",
      "items": [],
      "totals": {"subtotal": 0}
    },
    "capabilities": {
      "allowed_actions": ["browse", "add_cart", "checkout"],
      "ui_hints": {"show_catalog": true}
    }
  },
  "routing_hints": {
    "bot_lane": "bot:lane:custom",
    "intent_required": true,
    "route_version": "v1"
  }
}
```

---

## Configuration Reference

### Core Settings

```python
class Settings:
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Streams
    INCOMING_STREAM: str = "ingress:incoming"
    POLL_COUNT: int = 10  # Messages per poll
    POLL_BLOCK_MS: int = 1000  # Blocking timeout
    
    # Cache Controls
    CACHE_ENABLED: bool = True
    REDIS_KV_READ_ONLY: bool = False
    REDIS_STREAM_PUBLISH_ENABLED: bool = True
    
    # Cache TTLs
    BOT_CACHE_TTL_SECONDS: int = 3600
    USER_CACHE_TTL_SECONDS: int = 900
    CAPABILITIES_CACHE_TTL_SECONDS: int = 3600
    SESSION_CONTEXT_TTL_SECONDS: int = 1800
    
    # ICE Integration
    ICE_SERVICE_URL: str = ""  # (empty = disabled)
    ICE_PRELOAD_PATH: str = "/api/v1/hydrate/session"
    INGRESS_HYDRATE_FIRST: bool = False  # Enable preload-first mode
    
    # HTTP Fallback
    ENRICH_ALLOW_FALLBACK_HTTP: bool = True
```

---

## Message Flow Examples

### Example 1: Default Bot (Cache Hit)

```
1. Message arrives: from=260970000001, to=+260970000002
2. Bot lookup → cache HIT → bot_type=default
3. User lookup → skipped (not custom bot)
4. Capabilities → cache HIT
5. Session → cache HIT
6. Publish to bot:lane:default
```

**Total latency:** ~50ms (cache hits only)

### Example 2: Custom Bot (Cache Miss, ICE Preload)

```
1. Message arrives: from=260970000001, to=+260970000002
2. Bot lookup → cache MISS → call Bot Service → cache WRITE
3. User lookup → cache MISS → call Auth Service → cache WRITE
4. Capabilities → cache HIT
5. Session → cache MISS
6. (If INGRESS_HYDRATE_FIRST=true)
   └─ Call ICE /api/v1/hydrate/session → cache WRITE
7. Publish to bot:lane:custom
```

**Total latency:** ~200-500ms (HTTP calls + ICE)

### Example 3: Duplicate Detection

```
1. Same message arrives (same request_id)
2. Validator checks idempotency cache
3. Duplicate detected → SKIP (metrics.observe_duplicate)
4. Not published to streams
```

---

## Integration Points with ICE Service

### 1. Session Context Preload

Bot-ingress calls `POST /api/v1/hydrate/session` to ask ICE to:
- Compose session blob from all adapters
- Cache in Redis for fast lookups
- Return enriched context to ingress

### 2. Idempotency Tracking

Ingress maintains idempotency cache for request deduplication:
- Key: `idempotency:{request_id}`
- TTL: Configurable (default 24h)
- Prevents duplicate processing

### 3. Session Management

Ingress tracks active sessions in Redis:
- Key: `session:{session_id}`
- Contains: current node, last activity, mode, etc.
- Used by ICE for session validation during confirm/reserve

---

## Operational Considerations

### Scaling

- **Listener**: Single async loop per instance (can replicate)
- **Cache**: Shared Redis (no conflicts)
- **Publishing**: Fanout to multiple consumers on bot:lane:*

### Failure Modes

1. **Redis unavailable**: Queues back up in `ingress:incoming`
2. **Bot Service down**: HTTP timeout → fallback to default bot
3. **ICE down**: Preload fails gracefully → use cache-only path
4. **Invalid payload**: Sent to `ingress:dlq`

### Monitoring

- `metrics.observe_processed(duration)` - Track processing time
- `metrics.observe_duplicate()` - Track duplicate rate
- `metrics.observe_dlq()` - Track error rate
- Stream consumer lag - Watch with Redis CLI

---

## Next Integration Steps

1. **Configure ICE_SERVICE_URL** in bot-ingress environment
   ```bash
   ICE_SERVICE_URL=http://localhost:8000
   ```

2. **Test preload endpoint** from ingress
   ```bash
   curl -X POST http://localhost:8000/api/v1/hydrate/session \
     -H "Content-Type: application/json" \
     -d '{...}'
   ```

3. **Monitor Redis streams** for data flow
   ```bash
   redis-cli XLEN ingress:incoming
   redis-cli XLEN bot:lane:custom
   redis-cli XLEN ingress:resolved_payload
   ```

4. **Enable hydrate-first mode** (when ICE is stable)
   ```bash
   INGRESS_HYDRATE_FIRST=true
   ```

---

## Summary

Bot Ingress Service is a **high-performance message enrichment pipeline** that:

✅ Validates all inbound messages  
✅ Enriches with cache-first lookups  
✅ Integrates with ICE for session context  
✅ Publishes to bot-specific lanes  
✅ Maintains audit trail in resolved_payload  
✅ Handles errors gracefully (DLQ)  
✅ Supports read-only and offline modes  

**Ready for bot-facing deployments** with ICE as optional session context provider.
