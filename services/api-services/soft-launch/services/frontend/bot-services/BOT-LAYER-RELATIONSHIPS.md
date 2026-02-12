# Bot Services Layer — Relationship Diagram & Optimization Guide

**Status:** February 4, 2026  
**Scope:** Bot Services only (6 microservices + ICE integration)  
**Focus:** Data flow, dependencies, and performance optimization

---

## Service Map (6 Core Services)

```
┌────────────────────────────────────────────────────────────────┐
│ External Channels (SMS, WhatsApp, HTTP Callbacks)              │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │   BOT INGRESS SERVICE  │ ← Entry point, cache-first
        │  (Enrichment + Pub)    │
        │                        │
        │ Redis Streams:         │
        │ ├─ Input: ingress:in   │
        │ ├─ Output: bot:lane:*  │
        │ └─ Audit: ingress:*    │
        └────────────┬───────────┘
                     │
         ┌───────────┼───────────┐
         │           │           │
    ┌────▼──┐  ┌────▼──┐  ┌────▼──────┐
    │DEFAULT│  │INTENT │  │ CUSTOM    │
    │ BOT   │  │SERVICE│  │ BOT       │
    │       │  │       │  │ SERVICE   │
    │Rules- │  │LLM    │  │Node      │
    │driven │  │Gemini │  │Engine     │
    └───┬───┘  └───┬───┘  └────┬─────┘
        │          │            │
        │    ┌─────▼───┐   reply│requests
        │    │ Intent  │        │
        │    │ Results │        │
        │    └─────────┘        │
        │                       │
        └───────────┬───────────┘
                    │
                    ▼
        ┌────────────────────────┐
        │  BOT REPLY SERVICE     │ ← Response formatting
        │                        │
        │ Input: reply:requests  │
        │ Output: outbound:*     │
        └────────────┬───────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  OUTBOUND SERVICE      │ ← Channel delivery
        │                        │
        │ Input: outbound:*      │
        │ Output: (SMS/WA/HTTP)  │
        └────────────────────────┘


        ┌────────────────────────┐
        │  ICE SERVICE           │ ← Orchestration (Phase 4)
        │  (Order Choreography)  │
        │                        │
        │ Called by:             │
        │ ├─ Ingress (hydrate)   │
        │ ├─ Custom Bot (ops)    │
        │ └─ Default Bot (cart)  │
        └────────────────────────┘
```

---

## Detailed Data Flow

### Flow 1: Message Arrives → Ingress → Bot Type Routing

```
External Message (SMS/WhatsApp)
└─ normalize() → ingress:incoming stream entry
   ├─ event_id: evt_20251226_001
   ├─ session_id: sess_abc123
   ├─ from_: 260970000001
   ├─ to: +260970000002 (bot_id)
   └─ message_body: "show products"

↓ BOT INGRESS SERVICE (app/worker.py)

1. XREADGROUP from ingress:incoming
2. validate_and_check() → idempotency dedup
3. enrich_inbound():
   ├─ Bot lookup: cache:bot:{to}
   │  └─ MISS → Bot Service HTTP → cache WRITE
   ├─ User lookup (custom only): cache:user:{from}:{business_id}
   │  └─ MISS → Auth Service HTTP → cache WRITE
   ├─ Capabilities: cache:capabilities:{mode}
   │  └─ MISS → Capability Service HTTP → cache WRITE
   ├─ Session context (optional): cache:session_context:{session_id}
   │  └─ (Or call ICE POST /api/v1/hydrate/session)
   └─ Enrich payload with bot_meta, user, capabilities

4. publish_enriched():
   ├─ bot:lane:default ← if bot_type == "default"
   ├─ bot:lane:custom  ← if bot_type == "custom"
   └─ ingress:resolved_payload (audit)

5. XACK entry
```

**Caching Impact:**
- **Cache hits:** ~50ms total (Redis only)
- **Cache misses:** ~200-500ms (HTTP fallback + cache write)
- **TTLs:** bot (3600s), user (900s), capabilities (3600s), session (1800s)

---

### Flow 2A: DEFAULT Bot → Menu Navigation

```
bot:lane:default entry (enriched payload)
└─ Current node: "start"

↓ DEFAULT BOT SERVICE (lightweight state machine)

1. Load session state: cache:session:{session_id}
2. Load rules/templates for current_node
3. Evaluate: user_input + intent_required
   ├─ If intent_required=true:
   │  └─ Publish to intent:requests
   │     └─ (Intent Service responds on intent:results)
   └─ Else: Use template rules (no LLM)
4. Determine next_node + reply_template
5. (Optional) For cart operations:
   ├─ Load cache:order_draft:{session_id}
   ├─ Apply local mutation (add item, update qty)
   ├─ Optimistic CAS write
   └─ On conflict: rehydrate from ICE
6. Publish reply:requests
   ├─ event_id, session_id, template_id, template_vars
7. Update session state: cache:session (next_node, flags)
```

**Latency Breakdown (happy path):**
- Session load: ~5ms (Redis)
- Rules evaluation: ~1ms (in-memory)
- Reply publish: ~5ms (Redis)
- **Total: ~15ms**

**With Intent Call:**
- Add intent:requests publish: ~5ms
- Intent Service processes (2-5s Gemini call)
- intent:results consumed: ~5ms
- **Total: ~2-5s**

---

### Flow 2B: CUSTOM Bot → Node Engine (with OOB mutations)

```
bot:lane:custom entry (enriched payload)
└─ Current node: "serve_products"

↓ CUSTOM BOT SERVICE (Node Engine)

1. Idempotency check: idempotency:{event_id}
   ├─ If done: return cached result
   └─ Else: claim lock

2. Load OOB snapshot: oob:{session_id}
   ├─ If missing: create_default_if_missing()
   └─ Extract: cart.items, totals, status, lock_version

3. (Optional) Call Intent Service:
   ├─ Publish intent:requests
   └─ Wait for intent:results (blocking or async?)
      [OPTIMIZATION POINT 1]

4. Execute handler for current_node:
   ├─ Input: oob_snapshot, event, intent, enriched_meta
   ├─ Handler logic (in-process):
   │  ├─ Resolve SKUs, fetch prices
   │  ├─ (Optional) Call ICE:
   │  │  ├─ POST /api/v1/reserve (lock prices)
   │  │  ├─ POST /api/v1/confirm (payment)
   │  │  └─ POST /api/v1/payment_status (poll)
   │  ├─ Return oob_patch + next_node
   │  └─ [OPTIMIZATION POINT 2: handler latency]
   └─ Output: {oob_patch, side_effects, next_node}

5. Apply OOB patch (optimistic CAS):
   ├─ WATCH oob:{session_id}
   ├─ Read current version
   ├─ Increment lock_version
   ├─ MULTI/EXEC to write atomically
   ├─ On conflict (WATCH failed):
   │  └─ Retry up to 3 times with fresh snapshot
   └─ [OPTIMIZATION POINT 3: CAS conflict rate]

6. Publish outputs:
   ├─ reply:requests (event_id, session_id, text, next_node)
   └─ oob:audit (intent_ids, oob_patch, result)

7. Mark idempotency done: idempotency:{event_id}
```

**Latency Breakdown (complex flow):**
- Load OOB: ~10ms (Redis)
- Intent call (if needed): ~2-5s
- Handler execution (in-process): ~10-50ms
  - Price fetch: ~5-10ms
  - ICE calls (if needed): ~100-500ms per call
- OOB CAS apply: ~5-20ms
- Publish outputs: ~10ms
- **Total: 50ms (no intent/ICE) to 5s+ (with intent + ICE)**

---

### Flow 3: Reply Service → Outbound

```
reply:requests stream entries (from Default Bot or Custom Bot)
└─ event_id, session_id, text, next_node, template_vars

↓ BOT REPLY SERVICE

1. XREADGROUP from reply:requests
2. Load reply template: templates:{template_id}
3. Render template with template_vars
   ├─ Inject OOB refs (if provided)
   ├─ Format currency, localization
   └─ Handle attachments (images, buttons, etc)
4. Enrich with channel metadata
5. Publish outbound:requests
   ├─ channel: whatsapp | sms | http
   ├─ recipient: 260970000001
   ├─ rendered_text, attachments, quick_replies
6. XACK reply:requests entry
```

**Latency:**
- Template load: ~3ms (Redis)
- Rendering: ~5-10ms (in-process)
- Publish: ~5ms
- **Total: ~15ms**

---

### Flow 4: Intent Service (Gemini LLM Integration)

```
intent:requests stream (from Default Bot or Custom Bot)
└─ event_id, session_id, user_input, context, required_intents

↓ BOT INTENT SERVICE

1. XREADGROUP from intent:requests
2. Assemble context for Gemini:
   ├─ Load session blob: cache:session:{session_id}
   ├─ Load order blob: cache:order_draft:{session_id}
   ├─ Load bot meta: cache:bot:{bot_id}
   ├─ Build system prompt (merchant-specific instructions)
   └─ Construct message: {user_input, context}
3. Call Gemini API:
   ├─ Model: gemini-1.5-flash (fast) or gemini-pro (smarter)
   ├─ Timeout: 5s
   ├─ Retries: 2
   └─ [OPTIMIZATION POINT 4: token usage, context size]
4. Parse LLM response:
   ├─ Extract intent ID
   ├─ Extract confidence score
   ├─ Extract slots (parameters)
   └─ Validate against required_intents
5. Publish intent:results
   ├─ event_id, session_id, intent_id, confidence, slots
6. XACK entry
```

**Latency:**
- Context assembly: ~20-50ms (Redis reads)
- Gemini call: **1-5s** (network + model inference)
- Parse + publish: ~10ms
- **Total: 1-5s** (dominated by LLM)

---

## Service Dependencies Matrix

| Service | Depends On | Redis Streams (In) | Redis Streams (Out) | HTTP Calls |
|---|---|---|---|---|
| **Ingress** | Redis, Bot/Auth/Cap Services | `ingress:incoming` | `bot:lane:default`, `bot:lane:custom`, `ingress:resolved` | Bot Service, Auth Service, Capability Service, (optional) ICE |
| **Default Bot** | Redis, ICE (opt) | `bot:lane:default` | `reply:requests` | (optional) ICE |
| **Custom Bot** | Redis, Intent (opt), ICE | `bot:lane:custom` | `reply:requests`, `oob:audit` | (optional) Intent Service, ICE |
| **Intent Service** | Redis, Gemini API | `intent:requests` | `intent:results` | Gemini API |
| **Reply Service** | Redis | `reply:requests` | `outbound:requests` | None |
| **Outbound Service** | Redis | `outbound:requests` | (external) | SMS/WhatsApp/HTTP APIs |

---

## ICE Integration Points

### From Bot Ingress
- **Endpoint:** `POST /api/v1/hydrate/session` (optional preload)
- **When:** Cache miss or hydrate-first mode enabled
- **Purpose:** Preload session context (blobs)
- **Called:** ~5-10% of messages (cache-first strategy)

### From Default Bot
- **Endpoints:** 
  - `POST /api/v1/hydrate/session` (cache miss)
  - `POST /api/v1/reserve` (checkout flow)
  - `POST /api/v1/confirm` (payment confirmed)
  - `GET /api/v1/orders/{order_id}/payment_status` (poll)
- **When:** User navigates to checkout, confirms payment
- **Purpose:** Manage inventory + payment lifecycle

### From Custom Bot
- **Endpoints:** Same as Default Bot (reserve, confirm, payment_status)
- **When:** Handler calls ICE for authoritative operations
- **Purpose:** Lock prices, process payment, create order

---

## Critical Paths & Latency Profile

### Fastest Path (Default Bot, No Intent, No ICE)

```
Message → Ingress (50ms cache hit)
        → Default Bot (15ms, rule-based)
        → Reply Service (15ms)
        → Outbound (10ms)
        ━━━━━━━━━━━━━━━━━
        TOTAL: ~90ms
```

### Medium Path (Default Bot, With Intent, No ICE)

```
Message → Ingress (50ms)
        → Default Bot (15ms, intent required)
        → Intent Service (2-5s, Gemini)
        → Reply Service (15ms)
        → Outbound (10ms)
        ━━━━━━━━━━━━━━━━━
        TOTAL: 2-5s
```

### Slowest Path (Custom Bot, With Intent, With ICE, CAS Conflict)

```
Message → Ingress (500ms, cache miss + HTTP)
        → Custom Bot (50ms, load OOB)
        → Intent Service (2-5s, Gemini)
        → Handler + ICE (500ms, price lock)
        → OOB CAS (conflict, retry 1-3x: 50-100ms)
        → Reply Service (15ms)
        → Outbound (10ms)
        ━━━━━━━━━━━━━━━━━
        TOTAL: 3-6s
```

---

## Optimization Recommendations

### OPTIMIZATION 1: Intent Service Batching & Caching

**Problem:** Gemini API calls (1-5s) are the dominant latency source.

**Current:** One Gemini call per intent request (blocking).

**Recommendations:**

1. **Cache Intent Results** (QUICK WIN)
   ```
   Key: intent_cache:{user_input_hash}:{bot_id}
   TTL: 3600s
   
   Benefits:
   - Repeated intents (within same merchant) hit cache
   - ~90% cache hit rate for common phrases
   - ~1-5s → ~5ms
   ```

2. **Batch Multiple Intent Requests** (HIGH IMPACT)
   ```
   Instead of:
   - Publish intent:request → wait for result (blocking)
   
   Do:
   - Batch requests in memory (100ms window)
   - One Gemini API call for batch (faster than N calls)
   - Publish results back to all requesters
   
   Benefits:
   - 10 concurrent intents: 1 Gemini call vs 10
   - 1-5s → 1-5s but with 10x throughput
   ```

3. **Use Faster Model** (COST-BENEFIT)
   ```
   Current: gemini-pro (latency ~3-5s)
   Option: gemini-1.5-flash (latency ~1-2s, cheaper)
   
   Trade-off: Slightly lower accuracy, significantly faster
   Recommendation: Use flash for high-volume merchants, pro for complex intent
   ```

4. **Implement Streaming LLM Responses** (COMPLEX)
   ```
   Instead of waiting for full Gemini response:
   - Start consuming partial results
   - Publish early intent guesses
   - Refine on full response
   
   Benefit: Sub-second perceived latency
   Cost: Complex error handling, potential inconsistency
   ```

**Implementation Priority: HIGH (1 week, 2-5s → 1-2s impact)**

---

### OPTIMIZATION 2: Ingress Cache-First Strategy Tuning

**Problem:** Cache misses in Ingress cause 200-500ms latency spikes.

**Current:** Cache lookups with HTTP fallback + write-through.

**Recommendations:**

1. **Extend Cache TTLs** (QUICK WIN)
   ```
   Current:
   - bot cache: 3600s (1h)
   - user cache: 900s (15m)
   - capabilities: 3600s (1h)
   
   Recommended (if data change is infrequent):
   - bot cache: 86400s (24h) — bots rarely change
   - user cache: 1800s (30m) — user data changes more often
   - capabilities: 86400s (24h) — capabilities stable
   
   Benefit: Fewer HTTP fallbacks
   Risk: Stale data (mitigated by invalidation on change)
   ```

2. **Cache Warming on Startup** (MEDIUM EFFORT)
   ```
   On Ingress service startup:
   1. Load all active merchants' bot definitions
   2. Pre-populate cache:bot:{phone} for all bots
   3. Pre-populate cache:capabilities for all modes
   
   Benefit: ~100% cache hit for first hour
   Cost: Warm startup time ~2-5s
   ```

3. **Intelligent Fallback to Default Bot** (HIGH IMPACT)
   ```
   If Bot Service times out:
   - Don't block (no cache fallback)
   - Default to bot_type="default"
   - Cache {bot_id → bot_type=default}
   - User experiences default bot UX instead of timeout
   
   Benefit: Graceful degradation, no user-visible latency
   Risk: Wrong bot type routed to custom lane (mitigated by handler fallback)
   ```

4. **Conditional Cache Invalidation** (ADVANCED)
   ```
   On Bot Service config change:
   - Publish to Redis stream: `cache:invalidation`
   - Ingress subscribes: clear specific cache keys
   - No TTL expiry needed, immediate update
   
   Benefit: Cache consistency + full TTL utilization
   ```

**Implementation Priority: MEDIUM (2 weeks, 30-50% faster on cache misses)**

---

### OPTIMIZATION 3: Custom Bot OOB Concurrency Control

**Problem:** Optimistic CAS conflicts under high concurrency degrade performance.

**Current:** Retry up to 3 times on lock_version conflict.

**Recommendations:**

1. **Analyze Conflict Rate** (FIRST STEP)
   ```
   Metrics to track:
   - cas_attempts (histogram by retry count)
   - cas_conflicts (counter)
   - oob_mutation_latency (histogram, with/without conflict)
   
   Target: <5% conflict rate (1 in 20 updates)
   ```

2. **Implement Exponential Backoff** (QUICK WIN)
   ```
   Retry 1: immediate
   Retry 2: 10ms sleep
   Retry 3: 50ms sleep
   
   Benefit: Higher success rate on later retries
   Cost: Added latency on conflicts
   ```

3. **Use Shorter-Lived OOB Mutations** (ARCHITECTURAL)
   ```
   Current: All cart mutations go through one OOB snapshot
   
   Improvement:
   - Split cart into shardable items: items[i] per user+product
   - Only lock specific item version (finer-grained locking)
   - Totals computed from items on read (eventual consistency)
   
   Benefit: <1% conflict rate (only conflicts if same item added twice)
   Risk: Totals briefly stale, need eventual consistency model
   ```

4. **Async OOB Writes via Event Sourcing** (COMPLEX)
   ```
   Instead of:
   - Load OOB → mutate → CAS write
   
   Do:
   - Publish oob:events (event_id, mutation)
   - Background process: apply events, rebuild OOB snapshot
   - No conflicts (append-only events)
   
   Benefit: Unlimited concurrency, CQRS architecture
   Cost: Eventual consistency, complex replay logic
   ```

**Implementation Priority: MEDIUM (if conflict rate >10%, spend 1-2 weeks)**

---

### OPTIMIZATION 4: Intent Service Context Assembly

**Problem:** Large context payloads slow Gemini calls.

**Current:** Load full session blob + order blob + bot meta for every intent call.

**Recommendations:**

1. **Minimal Context Prompt** (QUICK WIN)
   ```
   Current context size: ~5KB (session + order + bot meta)
   
   Trim to essentials:
   - User: phone, name, locale
   - Cart: item count, total amount
   - Bot: bot_name, merchant_name
   - Recent intents: last 3 intents
   
   New size: ~500B
   
   Benefit: ~90% smaller token usage → faster + cheaper Gemini
   Trade-off: Lower context quality (test accuracy impact)
   ```

2. **Cache System Prompt** (MEDIUM EFFORT)
   ```
   System prompt is 90% static (merchant instructions)
   
   Instead of including full prompt each call:
   - Upload prompt once to Gemini File API
   - Reference file_id in subsequent calls
   - Reduces token usage by 50%
   
   Benefit: 40-50% faster Gemini calls
   Cost: New file upload on prompt change
   ```

3. **Intent Classification Pipeline** (ADVANCED)
   ```
   Route by intent type:
   - Simple intents (yes/no, menu selection) → regex rules
   - Complex intents (natural language) → Gemini
   
   Benefit: 80% of intents avoid Gemini (1-5s → <10ms)
   Cost: Maintain regex ruleset
   ```

**Implementation Priority: MEDIUM (2 weeks, 30-50% faster Gemini)**

---

### OPTIMIZATION 5: Redis Stream Consumer Efficiency

**Problem:** XREADGROUP + XAUTOCLAIM polling adds latency.

**Current:** 10ms sleep on empty reads, CLAIM_IDLE_MS=2000.

**Recommendations:**

1. **Increase Batch Size** (QUICK WIN)
   ```
   Current: XREADGROUP count=10
   Recommended: XREADGROUP count=100 (or dynamic based on queue depth)
   
   Benefit: Fewer XREAD syscalls, better throughput
   Risk: Higher latency per message if queue small
   Solution: Dynamic count based on queue depth
   ```

2. **Use Redis Streams Blocking Properly** (QUICK WIN)
   ```
   Current: XREADGROUP with block=1000 (1s timeout)
   
   When queue empty:
   - Worker sleeps 0.1s
   - Next XREADGROUP waits 1s
   - Total: 1.1s before detecting new message
   
   Improvement: Reduce sleep to 10ms (tighter loop)
   Benefit: 100ms latency for new messages
   ```

3. **Consumer Group Rebalancing** (MEDIUM)
   ```
   When scaling bot services horizontally:
   - Add new consumer to group
   - Old consumers rebalance (may be slow with large pending queue)
   
   Solution: Use Redis stream consumer group rebalancing hints
   Benefit: Faster scaling with less spike
   ```

**Implementation Priority: LOW (1-2 days, 10-20% throughput improvement)**

---

### OPTIMIZATION 6: ICE Service Call Efficiency

**Problem:** ICE calls (reserve, confirm, payment_status) add 100-500ms latency.

**Current:** Synchronous calls from handlers.

**Recommendations:**

1. **Request Coalescing** (HIGH IMPACT)
   ```
   Scenario: Same product reserved by 10 users simultaneously
   
   Current: 10 ICE /reserve calls
   
   Improvement:
   - First request: call ICE (500ms)
   - Requests 2-10: wait for first result (cached for 100ms)
   - Reuse reservation_id
   
   Benefit: 10x fewer ICE calls
   Cost: Temporary stale reservation sharing
   ```

2. **Async ICE Calls** (MEDIUM EFFORT)
   ```
   Split synchronous operations into async:
   
   Synchronous (blocking):
   - /reserve (needed for checkout)
   - /confirm (needed for payment)
   
   Asynchronous (fire-and-forget):
   - /payment_status polling (publish to ice:preload stream)
   - Handlers get result via callback (reply-service polls)
   
   Benefit: Handler doesn't wait for payment polling
   Cost: More complex state management
   ```

3. **ICE Response Caching** (QUICK WIN)
   ```
   Responses that are stable:
   - /reserve response (price lock valid for 1h)
   - /confirm response (order immutable after creation)
   
   Cache in Redis:
   - cache:ice_reserve:{order_id} TTL=3600s
   - cache:ice_order:{order_id} TTL=∞
   
   Benefit: Idempotent retries are instant
   Risk: Cache invalidation complexity
   ```

4. **Circuit Breaker for ICE** (MEDIUM)
   ```
   If ICE latency > 5s or error rate > 10%:
   - Stop calling ICE temporarily
   - Use stale cache + emit warning
   - Gracefully degrade (disable checkout, stay on browsing)
   
   Benefit: Prevent cascade failures
   Cost: Reduced functionality during ICE outage
   ```

**Implementation Priority: HIGH (3 weeks, 20-40% latency reduction if ICE is bottleneck)**

---

### OPTIMIZATION 7: Database Query Optimization (Postgres)

**Problem:** Ingress, Intent Service, and Reply Service make Postgres queries (catalog, templates, user data).

**Current:** Not detailed in bot services scope, but impacts overall latency.

**Recommendations:**

1. **Redis Caching Layer** (QUICK WIN)
   ```
   Query patterns:
   - SELECT * FROM templates WHERE template_id = ?
   - SELECT * FROM products WHERE sku = ?
   - SELECT * FROM users WHERE phone = ?
   
   Add Redis cache:
   - cache:template:{template_id}
   - cache:product:{sku}
   - cache:user:{phone}
   
   TTLs: 3600s (re-query if data changes)
   
   Benefit: 10-50ms → <5ms per query
   ```

2. **Materialized Views** (MEDIUM EFFORT)
   ```
   For high-cardinality queries (e.g., product catalog):
   - Create Redis sorted set: products:{merchant_id}
   - Recompute on product data change (event-driven)
   - Supports range queries, sorting
   
   Benefit: Full catalog in memory, <1ms lookup
   Cost: Eventual consistency window
   ```

**Implementation Priority: MEDIUM (depending on query volume)**

---

## Summary: Optimization Roadmap

| Priority | Optimization | Effort | Impact | Timeline |
|---|---|---|---|---|
| 🔴 **HIGH** | Intent result caching | 3 days | 50-70% faster intent calls | Week 1 |
| 🔴 **HIGH** | Intent batching | 1 week | 10x throughput, 1-2s latency | Week 2 |
| 🔴 **HIGH** | ICE async/coalescing | 3 weeks | 20-40% faster checkout | Week 3-4 |
| 🟡 **MEDIUM** | Ingress cache TTL tuning | 2 days | 30-50% fewer cache misses | Week 1 |
| 🟡 **MEDIUM** | Intent context trimming | 1 week | 30-50% faster Gemini calls | Week 2 |
| 🟡 **MEDIUM** | OOB CAS conflict analysis | 3 days (if needed) | Varies | Week 3 |
| 🟢 **LOW** | Stream consumer tuning | 1 day | 10-20% throughput | Week 4 |
| 🟢 **LOW** | Postgres query caching | 1-2 weeks | 5-10ms per catalog query | Week 4-5 |

---

## Monitoring & Metrics

### Key Metrics to Track

```
# Latency (histogram by service)
ingress.latency (p50, p95, p99)
ingress.cache_hit_rate (%)
default_bot.latency
custom_bot.latency
intent_service.latency (split: context + gemini + parse)
reply_service.latency
outbound_service.latency

# Throughput
messages_per_second (by bot type)
intent_requests_per_second
oob_mutations_per_second

# Errors
cache_miss_fallback_rate (%)
ice_error_rate (%)
intent_service_error_rate (%)
oob_cas_conflict_rate (%)
dlq_rate (messages per second)

# Resource Utilization
redis_memory_usage (by key pattern)
redis_cpu (%)
gemini_api_cost ($ per day)
ingress_http_calls_per_second
```

### Dashboard Queries (Prometheus/Grafana)

```
# 95th percentile latency by service
histogram_quantile(0.95, rate(service_latency_seconds[5m]))

# Cache hit ratio
rate(cache_hits[5m]) / (rate(cache_hits[5m]) + rate(cache_misses[5m]))

# Message processing rate
rate(messages_processed[1m])

# OOB conflict rate
rate(oob_cas_conflicts[1m])

# ICE call volume and error rate
rate(ice_calls[1m])
rate(ice_errors[1m])
```

---

## Conclusion

**Bot Services Layer is well-architected with:**

✅ Clear service boundaries (Ingress → Bot → Reply → Outbound)  
✅ Async Redis stream processing (high throughput)  
✅ Smart caching (cache-first strategy)  
✅ Idempotency support (safe retries)  
✅ DLQ for error handling  
✅ ICE integration points identified  

**Primary optimization opportunities:**

🔴 **Intent Service caching + batching** → 50-70% latency reduction  
🔴 **ICE coalescing + async** → 20-40% latency reduction for checkout  
🟡 **Context trimming + Ingress TTL tuning** → 30-50% faster on average  

**Estimated impact:**

- **Best case (all optimizations):** 2-5s → 500ms for complex flows
- **Realistic (top 3 optimizations):** 2-5s → 1-2s within 4 weeks
- **Quick win (Intent caching):** 2-5s → 1-2s within 1 week

**Next Steps:**
1. Deploy monitoring dashboard
2. Implement Intent result caching (week 1)
3. Implement Intent batching (week 2)
4. Analyze OOB CAS conflicts (week 3)
5. Implement ICE optimizations (weeks 3-4)
