# Phase 3 Complete: Reserve + Confirm Workflows

**Status:** ✅ **COMPLETE**  
**Date:** February 4, 2026  
**Scope:** Phase 3.2 (Reservation workflow) + Phase 3.3 (Order confirmation workflow)

---

## Overview

Phase 3 implements the two critical orchestration workflows that power the ICE service:

1. **Reserve Workflow** (`app/orchestration/reserve.py`): Atomically reserve inventory and create order drafts
2. **Confirm Workflow** (`app/orchestration/confirm.py`): Complete the payment → order → delivery → affiliate attribution chain

Both workflows are **production-ready** with:
- ✅ Single-flight locking (prevent concurrent operations)
- ✅ Idempotency (prevent duplicate reservations/confirmations)
- ✅ Two-tier persistence (Redis cache → Postgres source of truth)
- ✅ Negative caching (prevent retry storms on OUT_OF_STOCK)
- ✅ Comprehensive error handling (rollback, lock release, logging)
- ✅ Event emission (`ice:reserved`, `ice:confirmed`)

---

## Architecture

### Reserve Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                      RESERVE WORKFLOW                            │
└─────────────────────────────────────────────────────────────────┘
                                                                     
   1. Acquire lock (prevent concurrent reservations)                
          │                                                          
          ▼                                                          
   2. Check idempotency cache (prevent duplicates)                  
          │                                                          
          ▼                                                          
   3. Fetch cart draft (Redis → Postgres fallback)                 
          │                                                          
          ▼                                                          
   4. Call CartOrderAdapter.reserve_items()                         
      ↳ POST /cart/{id}/checkout                                    
          │                                                          
          ├─► ✅ RESERVED                                           
          │   ├─► 5. Create order_draft blob                        
          │   ├─► 6. Persist to Postgres                            
          │   ├─► 7. Cache in Redis (60m TTL)                       
          │   ├─► 8. Cache idempotency result (2h)                  
          │   └─► 9. Emit ice:reserved event                        
          │                                                          
          └─► ❌ OUT_OF_STOCK                                       
              ├─► Negative cache (5m)                               
              └─► Raise ValueError                                  
                                                                     
   10. Release lock (always)                                        
```

**Key Features:**
- **Atomic reservation**: All-or-nothing (reserve succeeds or fails cleanly)
- **Single-flight lock**: `reserve:{session_id}:{cart_id}` (60s TTL)
- **Idempotency**: `reserve_idem:{idempotency_key}` (2h cache)
- **Negative cache**: `reserve_failed:{cart_id}` (5m) prevents retry storms
- **Order draft blob**: Full cart snapshot + reservation metadata persisted
- **TTL strategy**: 60m Redis cache for hot order drafts

---

### Confirm Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                      CONFIRM WORKFLOW                            │
└─────────────────────────────────────────────────────────────────┘
                                                                     
   1. Acquire lock (prevent concurrent confirmations)               
          │                                                          
          ▼                                                          
   2. Check idempotency cache (prevent duplicates)                  
          │                                                          
          ▼                                                          
   3. Fetch order draft (validate status = RESERVED)                
          │                                                          
          ▼                                                          
   4. Create order + initiate payment                               
      ↳ CartOrderAdapter.confirm_order()                            
        ├─► POST /orders/create                                     
        └─► POST /orders/{id}/initiate_payment                      
          │                                                          
          ▼                                                          
   5. Create delivery task (non-blocking)                           
      ↳ DeliveryAdapter.create_delivery_task()                      
        └─► POST /delivery/initiate/{order_id}                      
                                                                     
          │                                                          
          ▼                                                          
   6. Emit affiliate attribution (non-blocking)                     
      ↳ AffiliateAdapter.emit_attribution_event()                   
        └─► POST /attribute/order                                   
          │                                                          
          ▼                                                          
   7. Persist order_confirmed blob to Postgres                      
          │                                                          
          ▼                                                          
   8. Persist delivery_task blob to Postgres                        
          │                                                          
          ▼                                                          
   9. Cache order_confirmed in Redis (30–120m TTL)                  
          │                                                          
          ▼                                                          
   10. Update order draft status to CONFIRMED                       
          │                                                          
          ▼                                                          
   11. Cache idempotency result (4h)                                
          │                                                          
          ▼                                                          
   12. Emit ice:confirmed event                                     
          │                                                          
          ▼                                                          
   13. Release lock (always)                                        
```

**Key Features:**
- **Multi-step orchestration**: Order → Payment → Delivery → Affiliate (all coordinated)
- **Single-flight lock**: `confirm:{order_draft_id}` (120s TTL)
- **Idempotency**: `confirm_idem:{idempotency_key}` (4h cache)
- **Non-blocking failures**: Delivery/affiliate failures don't block order confirmation
- **Order confirmed blob**: Full order + payment + delivery metadata persisted
- **TTL strategy**: 30–120m Redis cache (varies by payment status)

---

## Implementation Details

### Files Created

1. **`app/orchestration/reserve.py`** (~280 lines)
   - `ReservationWorkflow` class
   - `reserve_inventory()`: Main reservation workflow
   - `cancel_reservation()`: Cancel order draft workflow
   - Error handling: ValueError (OUT_OF_STOCK), RuntimeError (lock failure)

2. **`app/orchestration/confirm.py`** (~350 lines)
   - `ConfirmationWorkflow` class
   - `confirm_order()`: Main confirmation workflow (payment → delivery → affiliate)
   - `fetch_payment_status()`: Payment status polling workflow
   - `cancel_order()`: Order cancellation workflow
   - Error handling: ValueError (validation), RuntimeError (backend failures)

3. **`scripts/test_reserve_confirm_workflows.py`** (~250 lines)
   - Test 1: Reserve workflow - Success case
   - Test 2: Reserve workflow - Idempotency (duplicate prevention)
   - Test 3: Confirm workflow - Success case (end-to-end)
   - Test 4: Confirm workflow - With affiliate attribution
   - Test 5: Fetch payment status

---

## Workflow Methods

### ReservationWorkflow

```python
class ReservationWorkflow:
    async def reserve_inventory(
        session_id: str,
        cart_id: str,
        user_id: str,
        business_id: str,
        payment_method: str = "mobile_money",
        payment_number: Optional[str] = None,
        pickup_location: Optional[str] = None,
        delivery_location: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Reserve inventory atomically."""
        # Returns:
        # {
        #     "status": "RESERVED",
        #     "order_draft_id": "...",
        #     "reservation_ref": "...",
        #     "cart_id": "...",
        #     "total_amount_minor": 150000,
        #     "items_count": 3,
        #     "correlation_id": "..."
        # }
    
    async def cancel_reservation(
        order_draft_id: str,
        reason: str = "USER_CANCELLED",
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cancel a reservation."""
```

### ConfirmationWorkflow

```python
class ConfirmationWorkflow:
    async def confirm_order(
        order_draft_id: str,
        payment_details: Dict[str, Any],
        delivery_details: Optional[Dict[str, Any]] = None,
        affiliate_context: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Confirm order with payment → delivery → affiliate chain."""
        # Returns:
        # {
        #     "status": "CONFIRMED",
        #     "order_id": "...",
        #     "order_draft_id": "...",
        #     "payment_ref": "...",
        #     "delivery_id": "...",
        #     "delivery_code": "...",
        #     "total_amount_minor": 150000,
        #     "items_count": 3,
        #     "affiliate_attribution": True,  # or False if failed
        #     "correlation_id": "..."
        # }
    
    async def fetch_payment_status(
        order_id: str,
        payment_ref: str,
    ) -> Dict[str, Any]:
        """Fetch payment status and update order_confirmed blob."""
    
    async def cancel_order(
        order_id: str,
        reason: str = "USER_CANCELLED",
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cancel a confirmed order."""
```

---

## Edge Cases Handled

### Reserve Workflow

1. **Concurrent Reservations**
   - Lock key: `reserve:{session_id}:{cart_id}` (60s TTL)
   - If lock acquisition fails → `RuntimeError("Concurrent reservation detected")`

2. **Duplicate Reservations**
   - Idempotency cache: `reserve_idem:{idempotency_key}` (2h)
   - If cached → return cached result (no backend call)

3. **OUT_OF_STOCK**
   - Negative cache: `reserve_failed:{cart_id}` (5m)
   - Prevents retry storms on unavailable items
   - Raises `ValueError("Reservation failed: OUT_OF_STOCK")`

4. **Missing Cart Draft**
   - Checks Redis → Postgres fallback
   - If not found → `ValueError("Cart draft not found")`

5. **Backend Errors**
   - Wrapped in `RuntimeError("Reservation failed: {error}")`
   - Lock always released in `finally` block

### Confirm Workflow

1. **Concurrent Confirmations**
   - Lock key: `confirm:{order_draft_id}` (120s TTL)
   - If lock acquisition fails → `RuntimeError("Concurrent confirmation detected")`

2. **Duplicate Confirmations**
   - Idempotency cache: `confirm_idem:{idempotency_key}` (4h)
   - If cached → return cached result (no backend call)

3. **Invalid Order Draft Status**
   - Validates `status == "RESERVED"`
   - If not → `ValueError("Cannot confirm order in status: {status}")`

4. **Delivery Creation Failure**
   - Non-blocking: logs error but continues order confirmation
   - Order can proceed without delivery task (manual intervention)

5. **Affiliate Attribution Failure**
   - Non-blocking: logs error but continues order confirmation
   - Returns `affiliate_attribution: False` in result

6. **Payment Initiation Failure**
   - Blocking: order confirmation fails if payment initiation fails
   - Raises `RuntimeError("Order confirmation failed: {error}")`

7. **Missing Order Draft**
   - If order draft not found → `ValueError("Order draft not found")`

8. **Backend Errors**
   - Wrapped in `RuntimeError("Order confirmation failed: {error}")`
   - Lock always released in `finally` block

---

## Testing

### Test Suite: `scripts/test_reserve_confirm_workflows.py`

**Test 1: Reserve workflow - Success case**
- Create test cart with 2 items
- Reserve inventory via `ReservationWorkflow.reserve_inventory()`
- Assert: `status == "RESERVED"`, `order_draft_id` exists, cart ID matches
- Verify: Order draft persisted to Postgres, cached in Redis

**Test 2: Reserve workflow - Idempotency**
- Reserve inventory twice with same `idempotency_key`
- Assert: Both requests return same `order_draft_id`
- Verify: Idempotency cache working (no duplicate backend calls)

**Test 3: Confirm workflow - Success case (end-to-end)**
- Use reservation result from Test 1
- Confirm order via `ConfirmationWorkflow.confirm_order()`
- Assert: `status == "CONFIRMED"`, `order_id` exists, `payment_ref` exists
- Verify: Order confirmed blob + delivery task blob persisted, cached

**Test 4: Confirm workflow - With affiliate attribution**
- Create new reservation with test cart
- Confirm with affiliate context (real affiliate_id from DB)
- Assert: `status == "CONFIRMED"`, `order_id` exists
- Verify: Affiliate attribution attempted (may fail non-blocking)

**Test 5: Fetch payment status**
- Use confirmation result from Test 3
- Fetch payment status via `ConfirmationWorkflow.fetch_payment_status()`
- Assert: Payment status returned (e.g., "PENDING", "COMPLETED")
- Verify: Order confirmed blob updated if payment completed

**Run Tests:**
```bash
cd services/frontend/bot-services/ICE-service
python -m scripts.test_reserve_confirm_workflows
```

---

## Integration with Backend Services

### Reserve Workflow → Backend

1. **Cart Service** (`POST /cart/{id}/checkout`)
   - Request: `cart_id`, `payment_method`, `payment_number`, `pickup_location`, `delivery_location`
   - Response: `{"status": "RESERVED", "reservation_ref": "...", "order_draft_id": "..."}` OR `{"status": "FAILED", "reason": "OUT_OF_STOCK"}`

### Confirm Workflow → Backend

1. **Order-Delivery Service** (`POST /orders/create`)
   - Request: `user_id`, `business_id`, `items`, `total_amount_minor`, `pickup_location`, `delivery_location`
   - Response: `{"order_id": "...", "status": "pending_payment"}`

2. **Order-Delivery Service** (`POST /orders/{id}/initiate_payment`)
   - Request: `payment_method`, `payment_number`, `amount_minor`
   - Response: `{"payment_ref": "...", "status": "payment_initiated"}`

3. **Order-Delivery Service** (`POST /delivery/initiate/{order_id}`)
   - Request: `pickup_location`, `delivery_location`, `recipient_phone`
   - Response: `{"delivery": {"id": "...", "status": "pending"}, "delivery_code": "..."}`

4. **Affiliate Engine** (`POST /attribute/order`)
   - Request: `order_id`, `business_id`, `affiliate_id`, `amount_minor`, `metadata`
   - Response: `{"attribution_id": "...", "status": "success"}`

5. **Payment-Revenue Service** (`POST /pawapay/deposits/initiate`)
   - Request: `depositId`, `order_id`, `business_id`, `amount_minor`, `phoneNumber`
   - Response: `{"payment_ref": "...", "status": "pending"}`

6. **Payment-Revenue Service** (`GET /pawapay/deposits/{ref}`)
   - Response: `{"status": "PENDING" | "COMPLETED" | "FAILED", ...}`

---

## Database Schema (JSONB Blobs)

### order_draft Table

```sql
CREATE TABLE ice_blobs.order_draft (
    id UUID PRIMARY KEY,
    blob JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_order_draft_session_id ON ice_blobs.order_draft ((blob->>'session_id'));
CREATE INDEX idx_order_draft_cart_id ON ice_blobs.order_draft ((blob->>'cart_id'));
CREATE INDEX idx_order_draft_user_id ON ice_blobs.order_draft ((blob->>'user_id'));
CREATE INDEX idx_order_draft_status ON ice_blobs.order_draft ((blob->>'status'));
```

**Blob Structure:**
```json
{
    "session_id": "...",
    "cart_id": "...",
    "user_id": "...",
    "business_id": "...",
    "items": [...],
    "total_amount_minor": 150000,
    "payment_method": "mobile_money",
    "payment_number": "260970000001",
    "pickup_location": "Main Store",
    "delivery_location": "Customer Address",
    "reservation_ref": "...",
    "status": "RESERVED",  // RESERVED | CONFIRMED | CANCELLED
    "metadata": {
        "cart_snapshot": {...},
        "reservation_result": {...},
        "correlation_id": "...",
        "idempotency_key": "..."
    },
    "schema_version": "1.0",
    "updated_at": "2026-02-04T10:30:00Z"
}
```

### order_confirmed Table

```sql
CREATE TABLE ice_blobs.order_confirmed (
    id UUID PRIMARY KEY,
    blob JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_order_confirmed_order_id ON ice_blobs.order_confirmed ((blob->>'order_id'));
CREATE INDEX idx_order_confirmed_user_id ON ice_blobs.order_confirmed ((blob->>'user_id'));
CREATE INDEX idx_order_confirmed_payment_ref ON ice_blobs.order_confirmed ((blob->>'payment_ref'));
CREATE INDEX idx_order_confirmed_status ON ice_blobs.order_confirmed ((blob->>'status'));
```

**Blob Structure:**
```json
{
    "session_id": "...",
    "order_id": "...",
    "order_draft_id": "...",
    "user_id": "...",
    "business_id": "...",
    "items": [...],
    "total_amount_minor": 150000,
    "payment_method": "mobile_money",
    "payment_number": "260970000001",
    "payment_ref": "...",
    "payment_status": "PENDING",  // PENDING | COMPLETED | FAILED
    "delivery_id": "...",
    "delivery_code": "...",
    "pickup_location": "Main Store",
    "delivery_location": "Customer Address",
    "status": "CONFIRMED",  // CONFIRMED | CANCELLED
    "metadata": {
        "order_draft_snapshot": {...},
        "order_result": {...},
        "delivery_result": {...},
        "affiliate_context": {...},
        "attribution_success": true,
        "correlation_id": "...",
        "idempotency_key": "..."
    },
    "schema_version": "1.0",
    "updated_at": "2026-02-04T10:35:00Z"
}
```

### delivery_task Table

```sql
CREATE TABLE ice_blobs.delivery_task (
    id UUID PRIMARY KEY,
    blob JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_delivery_task_order_id ON ice_blobs.delivery_task ((blob->>'order_id'));
CREATE INDEX idx_delivery_task_delivery_id ON ice_blobs.delivery_task ((blob->>'delivery_id'));
CREATE INDEX idx_delivery_task_status ON ice_blobs.delivery_task ((blob->>'status'));
```

**Blob Structure:**
```json
{
    "order_id": "...",
    "delivery_id": "...",
    "delivery_code": "...",
    "pickup_location": "Main Store",
    "delivery_location": "Customer Address",
    "recipient_phone": "260970000001",
    "status": "INITIATED",  // INITIATED | CODE_SENT | CONFIRMED | FAILED
    "metadata": {
        "delivery_result": {...},
        "order_confirmed_id": "..."
    },
    "schema_version": "1.0",
    "updated_at": "2026-02-04T10:35:00Z"
}
```

---

## Redis Cache Keys

### Reserve Workflow

- **Lock:** `reserve:{session_id}:{cart_id}` (60s TTL)
- **Idempotency:** `reserve_idem:{idempotency_key}` (2h TTL)
- **Negative cache:** `reserve_failed:{cart_id}` (5m TTL)
- **Order draft:** `order_draft:{order_draft_id}` (60m TTL)

### Confirm Workflow

- **Lock:** `confirm:{order_draft_id}` (120s TTL)
- **Idempotency:** `confirm_idem:{idempotency_key}` (4h TTL)
- **Order confirmed:** `order_confirmed:{order_id}` (30–120m TTL based on payment status)
- **Delivery task:** `delivery_task:{delivery_id}` (60m TTL)

---

## Next Steps (Phase 4)

Now that Reserve + Confirm workflows are complete, the next phase is to expose these workflows via bot-facing API endpoints:

### Phase 4: Bot-Facing API Layer

1. **`POST /api/v1/hydrate/session`**
   - Hydrate session context (already implemented in Phase 2)
   - Returns: Hydrated session blob with user, business, catalog, affiliate context

2. **`POST /api/v1/reserve`**
   - Reserve inventory atomically
   - Body: `{"session_id": "...", "cart_id": "...", "user_id": "...", "business_id": "...", "payment_method": "...", "payment_number": "...", "idempotency_key": "..."}`
   - Returns: `{"status": "RESERVED", "order_draft_id": "...", "reservation_ref": "...", ...}`

3. **`POST /api/v1/confirm`**
   - Confirm order with payment → delivery → affiliate chain
   - Body: `{"order_draft_id": "...", "payment_details": {...}, "delivery_details": {...}, "affiliate_context": {...}, "idempotency_key": "..."}`
   - Returns: `{"status": "CONFIRMED", "order_id": "...", "payment_ref": "...", "delivery_id": "...", ...}`

4. **`GET /api/v1/orders/{order_id}/payment_status`**
   - Fetch payment status for confirmed order
   - Returns: `{"status": "PENDING" | "COMPLETED" | "FAILED", ...}`

5. **`POST /api/v1/orders/{order_id}/cancel`**
   - Cancel a confirmed order
   - Body: `{"reason": "USER_CANCELLED"}`
   - Returns: `{"status": "CANCELLED", "order_id": "...", ...}`

---

## Summary

**Phase 3 is complete** with production-ready reserve + confirm workflows:

✅ **Reserve Workflow** (`app/orchestration/reserve.py`)
- Atomic reservation with single-flight locks
- Idempotency (2h cache)
- Negative caching for OUT_OF_STOCK (5m)
- Order draft blob persistence (Postgres + Redis)
- Event emission (`ice:reserved`)

✅ **Confirm Workflow** (`app/orchestration/confirm.py`)
- Multi-step orchestration: order → payment → delivery → affiliate
- Non-blocking failures (delivery, affiliate)
- Idempotency (4h cache)
- Order confirmed + delivery task blob persistence
- Event emission (`ice:confirmed`)

✅ **Test Suite** (`scripts/test_reserve_confirm_workflows.py`)
- 5 comprehensive tests
- Real backend service integration
- Idempotency validation
- Edge case coverage

**Database:** 3 new JSONB tables (order_draft, order_confirmed, delivery_task) with smart indexing

**Redis Cache:** 8 new cache keys with TTL strategy (5m–4h based on use case)

**Ready for Phase 4:** Bot-facing API endpoints to expose reserve + confirm workflows to chatbot layer 🚀
