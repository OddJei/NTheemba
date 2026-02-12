# Custom Bot Service — Architecture & Integration Analysis

**Status:** Inspected February 4, 2026  
**Service Location:** `services/frontend/bot-services/custom-bot-service/`

---

## Overview

The Custom Bot Service is the **decision engine** for merchant-customized conversations. It:

1. **Consumes** enriched messages from Redis stream `bot:lane:custom` (from Bot Ingress)
2. **Resolves intents** via Intent Service (e.g., "add_item", "proceed_checkout")
3. **Executes handlers** that mutate Order Object (OOB) stored in Redis (cart, items, totals, fulfillment, payment)
4. **Publishes** side-effects to:
   - `reply:requests` — for Bot Reply Service (construct user response)
   - `oob:audit` — for audit trail and OOB reconstruction
   - `custom-bot:dlq` — for failed/unrecoverable states
5. **Calls ICE** for authoritative operations (price locks, inventory reservation, payment validation)

### Key Design Principle: **Order Object (OOB) as Source of Truth**

OOB is the canonical mutable state for an in-progress order. Handlers receive OOB snapshot, return atomic patches, Node Engine applies patches with optimistic concurrency control (CAS on `lock_version`).

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Redis Stream: bot:lane:custom                          │
│  (Enriched envelope from Bot Ingress)                   │
└──────────────────┬──────────────────────────────────────┘
                   │ XREADGROUP (custom-bot-workers)
                   ▼
        ┌──────────────────────────────────┐
        │  Stream Consumer (worker.py)     │
        │  └─ Async XREADGROUP loop        │
        │  └─ Claim pending entries        │
        │  └─ Ack on success / DLQ on fail │
        └────────────┬─────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────┐
        │  Entry Processor (processor.py)  │
        │  ├─ Parse payload                │
        │  ├─ Idempotency check            │
        │  ├─ Load OOB snapshot            │
        │  └─ Process event                │
        └────────────┬─────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────┐
        │  Runtime Engine (runtime_engine) │
        │  ├─ Intent parsing               │
        │  ├─ Handler lookup & execution   │
        │  ├─ OOB patch application (CAS)  │
        │  └─ Side-effects generation      │
        └────────────┬─────────────────────┘
                     │
         ┌───────────┼───────────┬──────────────┐
         ▼           ▼           ▼              ▼
     Redis Stream Redis Stream Redis Stream  ICE Service
     reply:       oob:audit    custom-bot:   (for auth
     requests               dlq         ops)
```

---

## Core Components

### 1. Stream Consumer (worker.py)

**Responsibilities:**
- Create consumer group if missing (`ensure_group`)
- Poll `bot:lane:custom` stream using `XREADGROUP`
- Claim pending/stale entries using `XAUTOCLAIM`
- Track attempt count per entry (`attempts:{stream}:{entry_id}`)
- Push to DLQ after max retries

**Configuration (env vars):**

```bash
CUSTOM_BOT_STREAM=bot:lane:custom
CUSTOM_BOT_CONSUMER_GROUP=custom-bot-workers
CUSTOM_BOT_CONSUMER_NAME=custom-bot-1  # per-instance unique
CUSTOM_BOT_DLQ_STREAM=custom-bot:dlq
CUSTOM_BOT_ATTEMPT_TTL_SECONDS=3600
CUSTOM_BOT_MAX_ATTEMPTS=3
CUSTOM_BOT_CLAIM_IDLE_MS=2000  # claim pending after 2s idle
```

**Processing Loop:**

```
1. XREADGROUP from bot:lane:custom
   ├─ If messages: process each
   ├─ If none: try XAUTOCLAIM (claim stale pending entries)
   └─ Loop with 0.1s sleep

2. For each entry:
   ├─ Call handle_entry()
   ├─ On success: XACK + optionally XDEL
   ├─ On error:
   │  ├─ Increment attempts counter
   │  ├─ If attempts >= MAX_ATTEMPTS: push to DLQ, XACK
   │  └─ Else: leave pending (will be claimed next cycle)
```

**Example Flow:**

```
Entry ID: 1234567890-0
Data: {
  "event_id": "evt_20251226_0001",
  "session_id": "sess_abc123",
  "inbound": {"text": "Add 2 solar panels"},
  ...
}

Attempt 1: Processing fails (ICE timeout)
  ├─ attempts:bot:lane:custom:1234567890-0 = 1
  └─ Entry remains in stream (pending)

Attempt 2 (on next claim cycle): Still fails
  ├─ attempts:bot:lane:custom:1234567890-0 = 2
  └─ Entry remains in stream (pending)

Attempt 3: Finally succeeds
  ├─ XACK 1234567890-0
  └─ XDEL 1234567890-0 (optionally)
```

---

### 2. Entry Processor (processor.py)

**Responsibilities:**
- Parse payload from stream entry (flexible JSON extraction)
- Extract key fields: `event_id`, `session_id`, `bot_type`
- Load OOB snapshot from Redis (create default if missing)
- Enforce idempotency (skip if already processed)
- Call runtime engine for processing
- Publish reply and audit events

**Payload Parsing:**

Tries multiple keys in order: `payload`, `data`, `message`, `body`

```python
# Input might be:
{
  "payload": "{\"event_id\":\"evt_123\",\"session_id\":\"sess_abc\",...}"
  # or
  "data": {...}
  # or flat message
  "event_id": "evt_123",
  "session_id": "sess_abc"
}
```

**Idempotency Check:**

```python
if event_id:
    # 1. Quick check: is this already done?
    if await idempotency.is_done(redis, event_id):
        logger.info("skipped_already_done")
        return
    
    # 2. Try to claim lock
    claimed = await idempotency.claim_lock(redis, event_id)
    if not claimed:
        # 3. Wait briefly for owner to finish
        for _ in range(3):
            if await idempotency.is_done(redis, event_id):
                return
            await asyncio.sleep(0.2)
        # 4. Race possible but proceed
```

**OOB Loading:**

```python
store = OOBStore()
oob, version = await store.create_default_if_missing(session_id)

# Extract for logging:
items_count = len(oob.get("cart", {}).get("items", []))
grand_total = oob.get("cart", {}).get("totals", {}).get("grand_total")
```

**Calling Runtime Engine:**

```python
result = await process_event(
    payload=payload,
    event_id=event_id,
    session_id=session_id
)
# Returns: {
#   "reply_text": str,
#   "next_node": str,
#   "intent_ids": [str],
#   "oob_ref": str  # reference to updated OOB in Redis
# }
```

**Publishing Side-Effects:**

```python
# Publish reply for Bot Reply Service
await publish_reply_request(
    redis,
    event_id=event_id,
    session_id=session_id,
    text=reply_text,
    next_node=next_node,
    oob_ref=oob_ref
)

# Publish audit for replay/audit trail
await publish_audit(
    redis,
    event_id=event_id,
    session_id=session_id,
    intent_ids=intent_ids,
    result=result
)
```

---

### 3. Order Object Store (oob_store.py)

**OOB Schema:**

```json
{
  "schema_version": "v1",
  "lock_version": 1,
  "last_event_id": null,
  "last_node_executed": null,
  "cart": {
    "items": [
      {"product_id": "p_123", "sku": "SKU123", "qty": 2, "unit_price_snapshot": 120.0, "total_price": 240.0}
    ],
    "totals": {
      "subtotal": 240.0,
      "discounts": 0,
      "delivery_fee": 50.0,
      "tax": 0,
      "grand_total": 290.0
    },
    "status": "building|reserved|locked|checkout_pending|completed|abandoned",
    "cart_version": 1
  },
  "metadata": {
    "fulfillment": {},
    "payment_ref": null,
    "delivery_id": null,
    "attribution": {}
  }
}
```

**Redis Storage:**

```
Key: oob:{session_id}
Type: Hash
Fields:
  - payload: <JSON string of OOB dict>
  - version: <int, monotonic>
```

**Optimistic Concurrency Control (CAS):**

```python
# Thread-safe update using WATCH/MULTI/EXEC
oob, current_version = await store.get_oob(session_id)

def updater(current_oob):
    # Apply mutation
    current_oob["cart"]["items"].append(new_item)
    current_oob["cart"]["totals"]["grand_total"] += 100
    return current_oob

new_oob, new_version = await store.cas_update(
    session_id,
    updater=updater,
    max_retries=3
)
```

On conflict (concurrent write detected):
- Reread OOB
- Re-run updater with latest snapshot
- Retry (up to max_retries)
- Raise `VersionConflict` if all retries fail

---

### 4. ICE Integration (ice_client.py)

**Configured via env vars:**

```bash
ICE_BASE_URL=http://localhost:8000
ICE_TIMEOUT=2.0  # seconds
ICE_MAX_RETRIES=2
```

**Available Endpoints Called by Custom Bot:**

| Method | Path | Purpose |
|---|---|---|
| `create_order()` | `POST /ice/order/create` | Create durable order record |
| `trigger_payment()` | `POST /ice/payment/trigger` | Initiate payment processing |
| `calculate_price()` | `POST /ice/cart/price` | Lock prices + compute totals |
| `get_payment_status()` | `POST /ice/payment/status` | Poll payment status |
| `validate_fulfillment_method()` | `POST /ice/fulfillment/validate` | Validate delivery method |

**Request Pattern (all endpoints):**

```python
await ice_client.create_order(
    session_id="sess_abc123",
    oob_ref="oob_ref_123",  # reference to OOB snapshot in Redis
    event_id="evt_20251226_0001",  # idempotency key
    extra={"custom_field": "value"}  # optional extra data
)
```

**Error Handling:**

```python
try:
    result = await ice_client.create_order(...)
except ValueError:
    # ICE not configured (base_url empty)
    pass
except ConnectionError:
    # Failed after max_retries
    # Handler marks action_status: fail
    pass
```

---

### 5. Publishing Outputs (publish.py)

**Output Stream 1: reply:requests** (for Bot Reply Service)

```json
{
  "event_id": "evt_20251226_0001",
  "session_id": "sess_abc123",
  "next_node": "serve_products",
  "text": "Great! I've added 2 Solar Panel A to your cart. Total is K290.",
  "refs": {
    "oob": "oob_snapshot_ref_123"
  },
  "meta": {},
  "trace_id": "trace_abc",
  "span_id": "span_xyz"
}
```

**Output Stream 2: oob:audit** (for Audit Service / Replay)

```json
{
  "event_id": "evt_20251226_0001",
  "session_id": "sess_abc123",
  "intent_ids": ["add_item"],
  "result": {
    "reply_text": "...",
    "next_node": "serve_products",
    "oob_patch": [
      {"op": "add", "path": "/cart/items/0", "value": {...}},
      {"op": "replace", "path": "/cart/totals/grand_total", "value": 290.0}
    ]
  },
  "trace_id": "trace_abc"
}
```

**Stream Routing:**

- `REPLY_STREAM`: configurable via `CUSTOM_BOT_REPLY_STREAM` (default `reply:requests`)
- `AUDIT_STREAM`: configurable via `CUSTOM_BOT_AUDIT_STREAM` (default `oob:audit`)

---

## Message Flow Examples

### Example 1: "Add Product to Cart"

```
1. Message arrives on bot:lane:custom
   {
     "event_id": "evt_001",
     "session_id": "sess_abc",
     "user_input": "Add 2 Solar Panel A",
     "intent": {"id": "add_item", "slots": {"product_id": "p_123", "qty": 2}}
   }

2. Worker picks up (XREADGROUP)
3. Processor loads OOB from Redis:
   {
     "cart": {
       "items": [],
       "totals": {"subtotal": 0, "grand_total": 0},
       "status": "building"
     }
   }

4. Runtime engine executes add_item handler:
   - Input: OOB snapshot, event, intent
   - Handler patches OOB:
     * Add item to cart.items
     * Recalculate totals
   - Output: (oob_patch, side_effects, next_node="serve_products")

5. OOBStore.cas_update() applies patch atomically:
   - Current version: 1
   - New version: 2
   - Updated cart.items: [{product_id: p_123, qty: 2, unit_price: 120, total: 240}]
   - Updated grand_total: 240

6. Publish reply:
   - Stream: reply:requests
   - Message: "Great! I've added 2 Solar Panel A. Total is K240."
   - next_node: serve_products

7. Publish audit:
   - Stream: oob:audit
   - Intent: add_item
   - OOB patch: [item addition + totals update]

8. Worker XACK entry from bot:lane:custom
```

### Example 2: "Proceed to Checkout" (ICE Call)

```
1. Message arrives on bot:lane:custom:
   {
     "event_id": "evt_002",
     "session_id": "sess_abc",
     "user_input": "Proceed to checkout",
     "intent": {"id": "checkout", "slots": {...}}
   }

2. Processor loads OOB:
   {
     "cart": {
       "items": [{product_id: p_123, qty: 2}],
       "totals": {"subtotal": 240},
       "status": "building",
       "cart_version": 2
     }
   }

3. Runtime engine executes checkout handler:
   - Calls ICE: await ice_client.calculate_price(
       session_id="sess_abc",
       oob_ref="oob_snapshot_ref_2"
     )
   - ICE returns: {"reserved_prices": {...}, "delivery_fees": {...}}
   - Handler patches OOB:
     * Lock prices in cart.items
     * Set cart.status = "reserved"
     * Store last_price_lock_id

4. OOBStore.cas_update() applies atomically:
   - Version 2 → 3
   - Cart status: reserved

5. Publish reply + audit as before

6. If ICE fails:
   - Handler catches error
   - Returns action_status: "fail" with diagnostics
   - next_node: "ask_correction"
   - OOB not modified
```

---

## Idempotency Strategy

**Idempotency Store (Redis):**

```
Key: idempotency:{event_id}
Fields:
  - lock: held during processing (TTL ~5s)
  - done: set after successful completion (TTL ~24h)
  - result: cached result if needed
```

**Flow:**

```python
# 1. Quick check
if await idempotency.is_done(redis, event_id):
    return cached_result

# 2. Try to claim lock (prevents duplicate processing)
claimed = await idempotency.claim_lock(redis, event_id)

# 3. Process (only if lock claimed)
if claimed:
    result = await process_event(...)
    await idempotency.mark_done(redis, event_id, result)

# 4. Release lock (automatic on timeout)
```

**Benefits:**
- Prevents duplicate handler execution if message retried
- Enables safe at-least-once processing semantics
- Works across multiple Custom Bot instances

---

## Failure Handling

### Transient Errors (ICE timeout, network)

```
Handler catches error → action_status: "fail"
├─ Mark in OOB for auditing
├─ Return diagnostics
├─ Suggest next_node: "ask_correction" or "retry_payment"
└─ OOB not modified (safe state)

Stream entry:
├─ Left pending (not ACK'd)
├─ Will be claimed on next XAUTOCLAIM cycle
├─ Attempt counter incremented
└─ Retried up to MAX_ATTEMPTS
```

### Permanent Errors (validation failure, policy denial)

```
Handler detects policy error → action_status: "denied"
├─ Log full diagnostics
├─ Publish to oob:audit for audit trail
├─ Suggest corrective next_node
└─ OOB patch with failure status

Stream entry:
├─ ACK'd (processing completed)
└─ Not in DLQ (recoverable via corrective node)
```

### Max Retries Exceeded

```
Attempt 1, 2, 3: All fail (ICE down, network issue)
├─ attempts:bot:lane:custom:{entry_id} = 3
├─ Push to custom-bot:dlq with:
│  ├─ original_stream: bot:lane:custom
│  ├─ original_entry_id: 1234567890-0
│  ├─ payload: {...full entry...}
│  └─ error: "ICE connection timeout"
├─ XACK entry (remove from active stream)
└─ DLQ entry reviewed by ops team
```

---

## Handler Interface Contract

**Input (Passed to Handler):**

```python
{
    "event_id": "evt_20251226_0001",
    "idempotency_key": "evt_20251226_0001",
    "session_id": "sess_abc123",
    "current_node": "serve_products",
    "user_input": "Add 2 of Solar Panel A",
    "intent_result": {
        "id": "add_item",
        "confidence": 0.92,
        "slots": {
            "product_id": "p_123",
            "quantity": 2
        }
    },
    "oob_snapshot": {
        "schema_version": "v1",
        "lock_version": 2,
        "cart": {
            "items": [],
            "totals": {"subtotal": 0, "grand_total": 0},
            "status": "building"
        }
    },
    "enriched_meta": {
        "bot_id": "bot_456",
        "bot_type": "custom",
        "schema_version": "1.0"
    }
}
```

**Output (Handler Returns):**

```python
{
    "node_executed": "serve_products",
    "action_status": "success",  # or "fail" / "denied"
    "oob_patch": [
        {
            "op": "add",
            "path": "/cart/items/0",
            "value": {
                "product_id": "p_123",
                "qty": 2,
                "unit_price_snapshot": 120.0,
                "total_price": 240.0
            }
        },
        {
            "op": "replace",
            "path": "/cart/totals/grand_total",
            "value": 240.0
        }
    ],
    "side_effects": [],  # future: ["send_sms", "log_event"]
    "next_node_suggestion": "serve_products",
    "diagnostics": {
        "items_added": 1,
        "price_locked": false
    }
}
```

**Handler Properties:**

- ✅ **Idempotent**: Given same `event_id`, always returns same result
- ✅ **Pure (mostly)**: Input → output (can call ICE for auth ops)
- ✅ **Non-mutating**: Returns patch, doesn't mutate input OOB
- ✅ **Atomic**: CAS apply ensures all-or-nothing
- ✅ **Diagnostic**: Explains why action failed

---

## ICE Integration Points

### 1. Cart Price Locking

**When:** User proceeds to checkout  
**Handler Calls:** `ice_client.calculate_price(session_id, oob_ref)`  
**Expected Response:** `{"reserved_prices": {...}, "delivery_fees": {...}, "reservation_id": "..."}`  
**OOB Update:** `cart.status = reserved`, `last_price_lock_id = reservation_id`

### 2. Payment Initiation

**When:** User submits payment method  
**Handler Calls:** `ice_client.trigger_payment(session_id, oob_ref, payment_method)`  
**Expected Response:** `{"payment_id": "...", "status": "pending"}`  
**OOB Update:** `metadata.payment_ref = payment_id`

### 3. Payment Polling

**When:** Waiting for payment callback  
**Handler Calls:** `ice_client.get_payment_status(payment_id, session_id)`  
**Expected Response:** `{"status": "completed|failed|pending", "amount": ...}`  
**OOB Update:** `metadata.payment_status = status`

### 4. Order Creation

**When:** Payment confirmed, order ready to fulfill  
**Handler Calls:** `ice_client.create_order(session_id, oob_ref)`  
**Expected Response:** `{"order_id": "...", "fulfillment_id": ...}`  
**OOB Update:** `metadata.order_id = order_id`

### 5. Fulfillment Validation

**When:** User selects delivery method  
**Handler Calls:** `ice_client.validate_fulfillment_method(session_id, method, details)`  
**Expected Response:** `{"valid": true, "estimated_delivery": "..."}` or `False`  
**OOB Update:** `metadata.fulfillment = details`

---

## Configuration Reference

**Environment Variables:**

```bash
# Redis
REDIS_URL=redis://localhost:6379/0

# Stream configuration
CUSTOM_BOT_STREAM=bot:lane:custom
CUSTOM_BOT_CONSUMER_GROUP=custom-bot-workers
CUSTOM_BOT_CONSUMER_NAME=custom-bot-1
CUSTOM_BOT_DLQ_STREAM=custom-bot:dlq
CUSTOM_BOT_REPLY_STREAM=reply:requests
CUSTOM_BOT_AUDIT_STREAM=oob:audit

# Retry configuration
CUSTOM_BOT_MAX_ATTEMPTS=3
CUSTOM_BOT_ATTEMPT_TTL_SECONDS=3600
CUSTOM_BOT_CLAIM_IDLE_MS=2000

# ICE integration
ICE_BASE_URL=http://localhost:8000
ICE_TIMEOUT=2.0
ICE_MAX_RETRIES=2
```

---

## Observability

**Structured Logging (processor.py):**

```
processing.entry: {
  stream: "bot:lane:custom",
  entry_id: "1234567890-0",
  event_id: "evt_20251226_0001",
  session_id: "sess_abc123",
  bot_type: "custom",
  oob: {
    items_count: 1,
    grand_total: 240.0,
    oob_version: 2
  }
}

entry_skipped_already_done: {
  event_id: "evt_20251226_0001"
}

processing_entry_failed: {
  stream: "bot:lane:custom",
  entry_id: "1234567890-0",
  error: "ConnectionError: ICE timeout"
}
```

**Metrics to Emit:**

- `custombot.processing.latency` — handler execution time (histogram by node)
- `custombot.handler.success_rate` — % of handlers succeeding
- `custombot.oob.conflicts` — CAS conflicts per second
- `custombot.ice.calls` — ICE call count (by endpoint)
- `custombot.dlq.count` — items in DLQ
- `custombot.idempotency.hits` — skipped due to already done

---

## Next Integration Steps

1. **Deploy Custom Bot Service** alongside Bot Ingress
   ```bash
   REDIS_URL=redis://localhost:6379/0 python -m app.main
   ```

2. **Configure ICE Integration:**
   ```bash
   ICE_BASE_URL=http://localhost:8000
   ICE_TIMEOUT=2.0
   ICE_MAX_RETRIES=2
   ```

3. **Monitor Redis Streams:**
   ```bash
   # Check incoming volume
   redis-cli XLEN bot:lane:custom
   
   # Check reply publishing
   redis-cli XLEN reply:requests
   
   # Check audit trail
   redis-cli XLEN oob:audit
   
   # Check DLQ
   redis-cli XLEN custom-bot:dlq
   ```

4. **Test Idempotency:**
   ```bash
   # Send same event_id twice, verify reply only published once
   # Verify oob:audit has single entry
   ```

5. **Validate Handler Execution:**
   ```bash
   # Monitor processing.entry logs
   # Verify OOB mutations (version increments)
   # Verify ICE calls succeed
   ```

---

## Summary

Custom Bot Service is a **high-performance node engine** that:

✅ Consumes enriched messages from `bot:lane:custom`  
✅ Loads OOB snapshots from Redis  
✅ Executes node handlers with intent-driven logic  
✅ Applies atomic patches to OOB (optimistic CAS)  
✅ Calls ICE for authoritative operations  
✅ Publishes replies and audit trail  
✅ Handles errors gracefully (DLQ, corrective nodes)  
✅ Supports idempotent retries  
✅ Scales via sharded streams and stateless handlers  

**Ready for production with ICE service integration.**
