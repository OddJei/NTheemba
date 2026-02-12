# ICE Service Integration Guide for Bot Services

**Purpose:** Help bot services (Ingress, Custom Bot, Default Bot) integrate with ICE service endpoints.

**Status:** February 4, 2026

---

## Quick Reference

### ICE Service Base URL
```
http://localhost:8000  (development)
http://ice-service:8000 (Docker/Kubernetes)
```

### API Version
```
/api/v1
```

### Health Checks
```
GET  /health          # Liveness probe (Redis + DB)
GET  /ready           # Readiness probe (dependencies)
```

---

## Integration Points by Bot Service

### 1. Bot Ingress Service

**Purpose:** Enrich inbound messages with session context

**Current Implementation:**
- Ingress calls ICE `POST /api/v1/hydrate/session` on cache miss
- Optional feature: enable with `INGRESS_HYDRATE_FIRST=true` for preload-first mode

**Integration Code Example:**

```python
# From bot-ingress-service/app/clients/ice_service.py

async def preload_session_context(
    http_client,
    settings,
    event_id: str,
    session_id: str,
    user_phone: str,
    bot_id: str,
    platform: str,
    bot_type: str,
    required_blobs: list[str] = None,
) -> dict | None:
    """Call ICE preload endpoint."""
    
    payload = {
        "event_id": event_id,
        "session_id": session_id,
        "user_phone": user_phone,
        "bot_id": bot_id,
        "platform": platform,
        "bot_type": bot_type,
        "required_blobs": required_blobs or ["session", "order_draft", "bot_meta"],
        "reason": "ingress_cache_miss"
    }
    
    try:
        url = f"{settings.ICE_SERVICE_URL}/api/v1/hydrate/session"
        resp = await http_client.post(url, json=payload, timeout=2.0)
        return resp.json() if resp.status_code == 200 else None
    except Exception:
        return None
```

**Configuration (Environment Variables):**
```bash
ICE_SERVICE_URL=http://ice-service:8000
INGRESS_HYDRATE_FIRST=false  # or true for preload-first mode
```

**Expected Response:**
```json
{
  "hydrated": true,
  "session_blob": {...},
  "order_draft_blob": {...},
  "bot_meta_blob": {...},
  "error": null
}
```

---

### 2. Custom Bot Service

**Purpose:** Execute node handlers with authoritative data (inventory, payment, etc.)

**Integration Points:**

#### a. Reserve Inventory (Checkout Initiation)

```python
# From custom-bot-service/app/handlers/checkout_handler.py

async def checkout_handler(oob_snapshot, event, ice_client):
    """Handle checkout node."""
    
    # Call ICE to lock prices/inventory
    reserve_payload = {
        "event_id": event["event_id"],
        "session_id": event["session_id"],
        "user_id": event["user_id"],
        "business_id": oob_snapshot.get("metadata", {}).get("business_id"),
        "cart_id": f"cart_{event['session_id']}",
        "payment_method": "mobile_money",
        "payment_number": "+260970000001",
        "idempotency_key": event["event_id"]
    }
    
    try:
        reserve_response = await ice_client.post(
            "/api/v1/reserve",
            json=reserve_payload
        )
        
        if reserve_response.status_code == 200:
            result = reserve_response.json()
            order_draft_id = result["order_draft_id"]
            
            # Update OOB with reservation details
            oob_patch = [
                {
                    "op": "replace",
                    "path": "/metadata/order_draft_id",
                    "value": order_draft_id
                },
                {
                    "op": "replace",
                    "path": "/cart/status",
                    "value": "reserved"
                }
            ]
            
            return {
                "oob_patch": oob_patch,
                "action_status": "success",
                "next_node": "confirm_payment",
                "diagnostics": {"reserved": True}
            }
    except Exception as e:
        # Handle error gracefully
        return {
            "oob_patch": [],
            "action_status": "fail",
            "next_node": "ask_correction",
            "diagnostics": {"error": str(e)}
        }
```

#### b. Confirm Order (Payment Confirmed)

```python
# From custom-bot-service/app/handlers/confirm_handler.py

async def confirm_handler(oob_snapshot, event, ice_client):
    """Handle order confirmation."""
    
    order_draft_id = oob_snapshot.get("metadata", {}).get("order_draft_id")
    
    confirm_payload = {
        "event_id": event["event_id"],
        "order_draft_id": order_draft_id,
        "user_id": event["user_id"],
        "payment_details": {
            "payment_method": "mobile_money",
            "phone_number": "+260970000001",
            "amount_minor": 100000
        },
        "delivery_details": {
            "method": "delivery",
            "address": "123 Main St"
        },
        "idempotency_key": event["event_id"]
    }
    
    try:
        confirm_response = await ice_client.post(
            "/api/v1/confirm",
            json=confirm_payload
        )
        
        if confirm_response.status_code == 200:
            result = confirm_response.json()
            order_id = result["order_id"]
            
            oob_patch = [
                {
                    "op": "replace",
                    "path": "/metadata/order_id",
                    "value": order_id
                },
                {
                    "op": "replace",
                    "path": "/metadata/payment_ref",
                    "value": result.get("payment_ref")
                },
                {
                    "op": "replace",
                    "path": "/cart/status",
                    "value": "confirmed"
                }
            ]
            
            return {
                "oob_patch": oob_patch,
                "action_status": "success",
                "next_node": "show_confirmation",
                "diagnostics": {"confirmed": True}
            }
    except Exception as e:
        return {
            "oob_patch": [],
            "action_status": "fail",
            "next_node": "ask_correction",
            "diagnostics": {"error": str(e)}
        }
```

#### c. Payment Status Polling

```python
# From custom-bot-service/app/handlers/payment_status_handler.py

async def poll_payment_status(session_id, order_id, ice_client):
    """Poll payment status from ICE."""
    
    try:
        response = await ice_client.get(
            f"/api/v1/orders/{order_id}/payment_status"
        )
        
        if response.status_code == 200:
            result = response.json()
            return {
                "order_id": result["order_id"],
                "status": result["payment_status"],  # COMPLETED|FAILED|PENDING
                "amount_minor": result["amount_minor"],
                "currency": result["currency"]
            }
    except Exception as e:
        return {"error": str(e)}
```

#### d. Cancel Order

```python
# From custom-bot-service/app/handlers/cancel_handler.py

async def cancel_order(session_id, order_id, reason, ice_client):
    """Cancel order through ICE."""
    
    payload = {
        "reason": reason  # USER_CANCELLED, PAYMENT_FAILED, TIMEOUT
    }
    
    try:
        response = await ice_client.post(
            f"/api/v1/orders/{order_id}/cancel",
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()  # {"status": "CANCELLED", "order_id": "..."}
    except Exception as e:
        return {"error": str(e)}
```

---

### 3. Default Bot Service

**Purpose:** Menu-driven bot with lightweight cart operations

**Integration:**

```python
# From default-bot-service/app/handlers/menu_handler.py

async def menu_handler(session_id, menu_node, user_input, ice_client):
    """Handle menu navigation with optional cart operations."""
    
    if menu_node == "add_to_cart":
        # Simple add-to-cart
        return {
            "template_id": "added_to_cart",
            "template_vars": {"product": "Solar Panel", "qty": 2},
            "next_node": "continue_shopping"
        }
    
    elif menu_node == "checkout":
        # Call ICE for cart reservation
        payload = {
            "event_id": f"evt_{uuid.uuid4().hex[:8]}",
            "session_id": session_id,
            "user_id": "user_xyz",
            "business_id": "biz_123",
            "cart_id": f"cart_{session_id}",
            "payment_method": "mobile_money",
            "payment_number": "+260970000001",
            "idempotency_key": f"evt_{uuid.uuid4().hex[:8]}"
        }
        
        try:
            response = await ice_client.post(
                "/api/v1/reserve",
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "template_id": "checkout_ready",
                    "template_vars": {
                        "total": "K290",
                        "items": 2
                    },
                    "next_node": "confirm_payment"
                }
            else:
                return {
                    "template_id": "checkout_failed",
                    "next_node": "menu_start"
                }
        except Exception:
            return {
                "template_id": "error",
                "next_node": "menu_start"
            }
```

---

## Error Handling

### Error Response Format

```json
{
  "error_code": "ICE_RESERVE_OUT_OF_STOCK",
  "message": "Requested quantity not available",
  "status": 400,
  "order_draft_id": null
}
```

### Error Codes & Handling

| Error Code | HTTP Status | Retry? | Suggested Action |
|---|---|---|---|
| `ICE_VALIDATION_ERROR` | 400 | No | Fix request payload |
| `ICE_HYDRATION_FAILED` | 500 | Yes | Retry with exponential backoff |
| `ICE_RESERVE_OUT_OF_STOCK` | 400 | No | Show correction node |
| `ICE_RESERVE_CONCURRENT_OP` | 409 | Yes | Retry immediately |
| `ICE_CONFIRM_DRAFT_NOT_FOUND` | 404 | No | Start over from reserve |
| `ICE_CONFIRM_PAYMENT_FAILED` | 400 | No | Ask for payment retry |
| `ICE_TEMPORARY_UNAVAILABLE` | 503 | Yes | Retry with backoff |
| `ICE_PAYMENT_INVALID` | 400 | No | Ask user to verify payment details |

### Retry Logic

```python
# Recommended retry strategy
MAX_RETRIES = 3
RETRY_BACKOFF = [0.1, 0.5, 2.0]  # seconds

async def call_ice_with_retry(func, *args, **kwargs):
    for attempt in range(MAX_RETRIES):
        try:
            return await func(*args, **kwargs)
        except ICEError as e:
            if not e.should_retry():
                raise
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_BACKOFF[attempt])
            else:
                raise
```

---

## Idempotency & Request Tracking

### Event ID Generation

```python
# All ICE requests must include event_id
import uuid
from datetime import datetime

def gen_event_id():
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    return f"evt_{timestamp}_{unique_id}"
```

### Idempotency Windows

| Endpoint | Window | Example |
|---|---|---|
| `/api/v1/hydrate/session` | 1 hour | Same event_id within 1h returns cached result |
| `/api/v1/reserve` | 2 hours | Same idempotency_key within 2h returns same reservation |
| `/api/v1/confirm` | 4 hours | Same idempotency_key within 4h returns same order |

### Safe Retry Pattern

```python
async def safe_reserve_with_idempotency(
    session_id: str,
    order_draft_id: str,
    idempotency_key: str,
    ice_client
) -> dict:
    """
    Call /reserve with idempotency.
    Safe to retry: same idempotency_key returns same result.
    """
    
    payload = {
        "event_id": idempotency_key,
        "session_id": session_id,
        "order_draft_id": order_draft_id,
        "idempotency_key": idempotency_key  # Exact same key
    }
    
    # First attempt
    response = await ice_client.post("/api/v1/reserve", json=payload)
    result = response.json()
    
    # Save idempotency_key in Redis
    await redis.setex(
        f"idempotency:{idempotency_key}",
        2 * 3600,  # 2 hour TTL
        json.dumps(result)
    )
    
    # On timeout/network error, retry is safe
    # ICE will recognize idempotency_key and return same result
    
    return result
```

---

## Tracing & Correlation

### Propagate Correlation ID

```python
# Generate or receive correlation_id
correlation_id = request.headers.get("X-Correlation-ID") or gen_event_id()

# Pass to ICE
headers = {
    "X-Correlation-ID": correlation_id,
    "X-Request-ID": event_id
}

response = await ice_client.post(
    "/api/v1/reserve",
    json=payload,
    headers=headers
)

# Log with correlation_id for tracing
logger.info("reserve_response", 
    event_id=event_id,
    correlation_id=correlation_id,
    status=response.status_code
)
```

---

## Monitoring Integration

### Metrics to Track

```python
# Track latency
start = time.time()
response = await ice_client.post("/api/v1/reserve", json=payload)
duration = time.time() - start

# Export to Prometheus
from app.observability.metrics import reserve_latency, reserve_requests

reserve_latency.observe(duration)
reserve_requests.labels(status="success").inc()
```

### Health Check Integration

```python
async def check_ice_service_health(ice_client):
    """Before making requests, verify ICE is ready."""
    
    try:
        response = await ice_client.get("/ready")
        return response.status_code == 200
    except Exception:
        return False
```

---

## Testing Integration

### Mock ICE for Unit Tests

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_checkout_handler():
    """Test checkout handler with mocked ICE."""
    
    mock_ice_client = AsyncMock()
    mock_ice_client.post.return_value = AsyncMock(
        status_code=200,
        json=lambda: {
            "status": "RESERVED",
            "order_draft_id": "ord_123",
            "reservation_ref": "ref_xyz"
        }
    )
    
    result = await checkout_handler(
        oob_snapshot={},
        event={"event_id": "evt_001", "session_id": "sess_001"},
        ice_client=mock_ice_client
    )
    
    assert result["action_status"] == "success"
    mock_ice_client.post.assert_called_once()
```

### Integration Tests with Real ICE

```bash
# Start ICE service
docker run -d -p 8000:8000 ice-service:latest

# Run integration tests
pytest tests/integration/ -v --timeout=30
```

---

## Performance Tips

1. **Cache Reserve Results:** Don't call /reserve twice for same cart
   ```python
   cache_key = f"reserved:{session_id}"
   if await redis.exists(cache_key):
       return await redis.get(cache_key)
   ```

2. **Batch Related Operations:** Minimize round-trips
   ```python
   # Good: one reserve call
   # Bad: hydrate → reserve → confirm separately
   ```

3. **Use Async:** Never block on ICE calls
   ```python
   # Good: await ice_client.post(...)
   # Bad: requests.post(...) [sync]
   ```

4. **Implement Timeouts:** Prevent hanging
   ```python
   response = await httpx.post(..., timeout=2.0)
   ```

---

## Support & Debugging

### Verify ICE is Running

```bash
# Health check
curl http://localhost:8000/health

# Readiness check
curl http://localhost:8000/ready

# Swagger docs
curl http://localhost:8000/docs
```

### Debug Failed Requests

```bash
# Enable debug logging
LOG_LEVEL=DEBUG python -m your_bot_service

# Check ICE logs
docker logs ice-service

# Tail Redis streams
redis-cli XREAD BLOCK 1000 STREAMS ice:hydrated 0
```

### Common Integration Issues

| Issue | Solution |
|---|---|
| Connection refused | Verify ICE_SERVICE_URL in environment |
| Timeout errors | Increase timeout, check ICE performance |
| Idempotency mismatch | Ensure same event_id for retries |
| OOB parse error | Verify oob_patch JSON format |

---

## Conclusion

**Bot services can confidently integrate with ICE by:**
- Using the 7 documented endpoints
- Following error handling guidelines
- Implementing idempotency for safe retries
- Propagating correlation IDs for tracing
- Monitoring ICE health before requests
- Testing with mocked and real ICE

**For questions:** Refer to [PRODUCTION-READY.md](PRODUCTION-READY.md) or [PHASE4-INGRESS.md](PHASE4-INGRESS.md).
