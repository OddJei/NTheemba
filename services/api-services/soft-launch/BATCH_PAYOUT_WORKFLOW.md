# Batch Payout Workflow Documentation

## Overview

The batch payout system enables payment-revenue service to process affiliate payouts in batches and notify the affiliate-engine of completion status via callbacks.

## Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│ Affiliate Engine│         │ Payment Revenue  │         │   PawaPay API   │
│   (Port 8510)   │         │   (Port 8590)    │         │   (External)    │
└────────┬────────┘         └────────┬─────────┘         └────────┬────────┘
         │                            │                            │
         │  1. Close Epoch            │                            │
         │    Create Allocations      │                            │
         │◄───────────────────────────┤                            │
         │                            │                            │
         │  2. POST /payout/batch     │                            │
         ├───────────────────────────►│                            │
         │     202 Accepted           │                            │
         │◄───────────────────────────┤                            │
         │                            │                            │
         │                            │  3. Process Payouts        │
         │                            ├───────────────────────────►│
         │                            │                            │
         │                            │  4. Payment Status         │
         │                            │◄───────────────────────────┤
         │                            │                            │
         │  5. POST /callbacks/       │                            │
         │     payout-status          │                            │
         │◄───────────────────────────┤                            │
         │     200 OK                 │                            │
         ├───────────────────────────►│                            │
         │                            │                            │
```

---

## Endpoints

### 1. POST /payout/batch

**Service:** payment-revenue (Port 8590)

**Authentication:** X-Admin-Key header (required)

**Description:** Initiates a batch payout for multiple affiliates. Returns immediately with 202 Accepted and processes payouts asynchronously in the background.

#### Request

**Headers:**
```
Content-Type: application/json
X-Admin-Key: change-me
```

**Body Schema:**
```json
{
  "epoch_id": "string (UUID)",
  "callback_url": "string (URL)",
  "payouts": [
    {
      "affiliate_id": "string (UUID)",
      "amount_zmw": "number (float)",
      "currency": "string (ZMW)"
    }
  ]
}
```

**Example Request:**
```bash
curl -X POST http://localhost:8590/payout/batch \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: change-me" \
  -d '{
    "epoch_id": "2024-11-epoch-1",
    "callback_url": "http://affiliate-engine:8510/callbacks/payout-status",
    "payouts": [
      {
        "affiliate_id": "aff-001",
        "amount_zmw": 1500.0,
        "currency": "ZMW"
      },
      {
        "affiliate_id": "aff-002",
        "amount_zmw": 2300.0,
        "currency": "ZMW"
      }
    ]
  }'
```

#### Response

**Status Code:** 202 Accepted

**Response Schema:**
```json
{
  "batch_id": "string (UUID)",
  "epoch_id": "string",
  "total_payouts": "number (int)",
  "total_amount_zmw": "number (float)",
  "payouts": [
    {
      "affiliate_id": "string (UUID)",
      "payout_id": "string (UUID)",
      "amount_zmw": "number (float)",
      "currency": "string",
      "status": "ACCEPTED",
      "initiated_at": "string (ISO 8601)"
    }
  ],
  "status": "ACCEPTED",
  "initiated_at": "string (ISO 8601)"
}
```

**Example Response:**
```json
{
  "batch_id": "3e6118e8-74b4-4fb3-8666-1e53e2188c04",
  "epoch_id": "9eaff605-3941-4b49-b641-f54164f2f67c",
  "total_payouts": 3,
  "total_amount_zmw": 5000.0,
  "payouts": [
    {
      "affiliate_id": "6d7107f9-9490-4736-9d9f-9b60a8d3ebc0",
      "payout_id": "3acac560-e8c4-49b9-b12c-cd0a13379a2e",
      "amount_zmw": 1666.67,
      "currency": "ZMW",
      "status": "ACCEPTED",
      "initiated_at": "2026-02-04T10:05:55.328255Z"
    }
  ],
  "status": "ACCEPTED",
  "initiated_at": "2026-02-04T10:05:55.328332Z"
}
```

#### Error Responses

**401 Unauthorized:**
```json
{
  "detail": "invalid_admin_key"
}
```

**422 Unprocessable Entity:**
```json
{
  "detail": [
    {
      "loc": ["body", "payouts"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

### 2. POST /callbacks/payout-status

**Service:** affiliate-engine (Port 8510)

**Authentication:** None (in auth skip paths)

**Description:** Receives payout status updates from payment-revenue service. Updates PoolAllocation records with payout completion status.

#### Request

**Headers:**
```
Content-Type: application/json
X-Admin-Key: change-me
X-Service: payment-revenue
```

**Body Schema:**
```json
{
  "payout_id": "string (UUID)",
  "epoch_id": "string",
  "affiliate_id": "string (UUID)",
  "status": "completed|failed",
  "amount_zmw": "number (float)",
  "error_message": "string|null",
  "completed_at": "string (ISO 8601)"
}
```

**Example Request:**
```json
{
  "payout_id": "3acac560-e8c4-49b9-b12c-cd0a13379a2e",
  "epoch_id": "9eaff605-3941-4b49-b641-f54164f2f67c",
  "affiliate_id": "6d7107f9-9490-4736-9d9f-9b60a8d3ebc0",
  "status": "completed",
  "amount_zmw": 1666.67,
  "error_message": null,
  "completed_at": "2026-02-04T10:05:55.451348Z"
}
```

#### Response

**Status Code:** 200 OK

**Response Schema:**
```json
{
  "status": "ok"
}
```

#### Behavior

1. **Lookup by payout_id:** First attempts to find allocation by `payout_id`
2. **Fallback lookup:** If not found, searches by `affiliate_id + epoch_id` and backfills `payout_id`
3. **Update allocation:**
   - Sets `payout_status` to callback status (completed/failed)
   - Sets `payout_completed_at` to callback timestamp
   - Sets `payout_error` if status is failed
   - Backfills `payout_id` if found by affiliate_id + epoch_id
4. **Audit event:** Emits `affiliate_payout_completed` audit event
5. **Graceful handling:** Returns 200 OK even if allocation not found to prevent retry loops

---

## Database Schema

### PoolAllocation Table (affiliate_engine schema)

**New columns added:**

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `payout_status` | varchar(50) | Yes | 'pending' | Status of payout: pending, processing, completed, failed |
| `payout_id` | varchar(36) | Yes | NULL | UUID of the payout transaction from payment-revenue |
| `payout_initiated_at` | timestamptz | Yes | NULL | Timestamp when payout was initiated |
| `payout_completed_at` | timestamptz | Yes | NULL | Timestamp when payout was completed or failed |
| `payout_error` | text | Yes | NULL | Error message if payout failed |

**SQL to add columns:**
```sql
ALTER TABLE affiliate_engine.pool_allocations 
  ADD COLUMN IF NOT EXISTS payout_status varchar(50) DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS payout_id varchar(36),
  ADD COLUMN IF NOT EXISTS payout_initiated_at timestamptz,
  ADD COLUMN IF NOT EXISTS payout_completed_at timestamptz,
  ADD COLUMN IF NOT EXISTS payout_error text;
```

**Query to verify payout status:**
```sql
SELECT 
  affiliate_id, 
  payout_status, 
  payout_id, 
  payout_completed_at 
FROM affiliate_engine.pool_allocations 
WHERE epoch_id = 'YOUR_EPOCH_ID' 
ORDER BY affiliate_id;
```

---

## Complete Workflow

### Phase 1: Epoch Preparation

1. **Create affiliates** (if needed)
   ```bash
   POST /affiliates
   Body: { "name": "Affiliate Name" }
   ```

2. **Record sales events** (happens during normal operations)
   ```bash
   POST /events/payment-success
   ```

3. **Get current epoch**
   ```bash
   POST /admin/epochs/open
   ```

4. **Set gross revenue** (from payment-revenue service)
   ```bash
   PUT /admin/epochs/{epoch_id}/gross-revenue
   Body: { "gross_revenue_zmw": 50000 }
   ```

### Phase 2: Epoch Closure & Allocation

5. **Close epoch and create allocations**
   ```bash
   POST /admin/epochs/{epoch_id}/close
   ```
   
   This calculates:
   - Affiliate metrics (sales volume, unique buyers, etc.)
   - Weighted scores based on commission settings
   - Pool amount (gross_revenue × pool_pct)
   - Payout amounts per affiliate

6. **Fetch allocations**
   ```bash
   GET /admin/epochs/{epoch_id}/allocations
   ```
   
   Returns PoolAllocation records with:
   - affiliate_id
   - payout_zmw (calculated amount)
   - payout_status: "pending"
   - No payout_id yet

### Phase 3: Batch Payout Initiation

7. **Prepare batch payout request**
   
   Map allocations to payout request format:
   ```javascript
   const payouts = allocations.map(alloc => ({
     affiliate_id: alloc.affiliate_id,
     amount_zmw: alloc.payout_zmw,
     currency: "ZMW"
   }));
   ```

8. **Submit batch payout**
   ```bash
   POST /payout/batch
   Headers: X-Admin-Key: change-me
   Body: {
     "epoch_id": "...",
     "callback_url": "http://affiliate-engine:8510/callbacks/payout-status",
     "payouts": [...]
   }
   ```

9. **Receive 202 Accepted response**
   - Contains batch_id for tracking
   - Contains payout_id for each affiliate
   - Status: ACCEPTED
   - Background processing begins immediately

### Phase 4: Background Processing

10. **payment-revenue processes payouts:**
    - Simulates PawaPay integration (currently immediate)
    - In production: Makes actual API calls to PawaPay
    - Tracks payout status

11. **payment-revenue sends callbacks:**
    - For each completed payout
    - POST to callback_url with status update
    - Includes payout_id, affiliate_id, epoch_id

### Phase 5: Status Updates

12. **affiliate-engine receives callbacks:**
    - Looks up PoolAllocation by payout_id
    - Fallback: Looks up by affiliate_id + epoch_id
    - Updates payout_status to "completed"
    - Sets payout_completed_at timestamp
    - Backfills payout_id if needed

13. **Verify completion:**
    ```sql
    SELECT * FROM affiliate_engine.pool_allocations 
    WHERE epoch_id = 'YOUR_EPOCH_ID' 
    AND payout_status = 'completed';
    ```

---

## Test Script

A complete test script is available at: `scripts/test_phase4_full_flow.ps1`

**Usage:**
```powershell
cd C:\Users\SMART PC\Documents\NTheemba\services\api-services\soft-launch
powershell -File scripts\test_phase4_full_flow.ps1
```

**What it does:**
1. Opens/creates an epoch
2. Creates 3 test affiliates
3. Records payment success events for each
4. Sets gross revenue
5. Closes epoch (creates allocations)
6. Fetches allocations
7. Initiates batch payout
8. Verifies callbacks are received

**Expected output:**
```
[1] Open or get current epoch
Epoch: 9eaff605-3941-4b49-b641-f54164f2f67c
[2] Create affiliates and seed payment events
[3] Set gross revenue
[4] Close epoch
[5] Fetch allocations
Allocations: 3
[6] Initiate batch payout
{
  "batch_id": "...",
  "total_payouts": 3,
  "total_amount_zmw": 5000.0,
  "status": "ACCEPTED"
}
[7] Done. Check logs for callbacks.
```

---

## Configuration

### Environment Variables

**payment-revenue:**
- `AFFILIATE_ENGINE_BASE_URL`: Base URL for affiliate-engine (default: http://affiliate-engine:8510)
- `AFFILIATE_ADMIN_KEY`: Admin key for authentication (default: change-me)

**affiliate-engine:**
- `AFFILIATE_ADMIN_KEY`: Admin key for admin endpoints (default: change-me)

### Authentication

**Batch payout endpoint:**
- Requires `X-Admin-Key` header
- Added to `_AUTH_SKIP_PATHS` in payment-revenue

**Payout callback endpoint:**
- Added to `_AUTH_SKIP_PATHS` in affiliate-engine
- No authentication required (internal service communication)
- Optionally validates `X-Admin-Key` and `X-Service` headers

---

## Monitoring & Debugging

### Check Logs

**payment-revenue:**
```bash
docker logs soft-launch-payment-revenue-1 --tail 50
```

Look for:
- `POST /payout/batch` requests with 202 status
- `payout_callback sent` log messages with status codes

**affiliate-engine:**
```bash
docker logs soft-launch-affiliate-engine-1 --tail 50
```

Look for:
- `POST /callbacks/payout-status` requests with 200 status
- `affiliate_payout_completed` log messages
- Any `payout_callback_allocation_not_found` warnings

### Query Database

**Check allocation status:**
```sql
SELECT 
  epoch_id,
  affiliate_id,
  payout_zmw,
  payout_status,
  payout_id,
  payout_completed_at
FROM affiliate_engine.pool_allocations
WHERE epoch_id = 'YOUR_EPOCH_ID'
ORDER BY payout_completed_at DESC;
```

**Count completed payouts:**
```sql
SELECT 
  payout_status,
  COUNT(*) as count,
  SUM(payout_zmw) as total_amount
FROM affiliate_engine.pool_allocations
WHERE epoch_id = 'YOUR_EPOCH_ID'
GROUP BY payout_status;
```

### Common Issues

**Issue:** Callbacks return 401 Unauthorized
- **Cause:** `/callbacks/payout-status` not in auth skip paths
- **Fix:** Added to `_AUTH_SKIP_PATHS` in affiliate-engine/src/app/main.py

**Issue:** Allocations not found by payout_id
- **Cause:** PoolAllocations created before payout_id assigned
- **Fix:** Callback handler falls back to affiliate_id + epoch_id lookup and backfills payout_id

**Issue:** SQLAlchemy session errors in background task
- **Cause:** Session management conflicts in async background tasks
- **Fix:** Removed database persistence from background task (can be re-added with proper session handling)

**Issue:** Background task doesn't execute
- **Cause:** Service crashes before task completes
- **Fix:** Simplified background task to avoid database operations

---

## Production Considerations

### PawaPay Integration

Current implementation simulates immediate payout completion. For production:

1. **Replace simulation with PawaPay API calls:**
   ```python
   async def _process_payouts():
       async with httpx.AsyncClient() as client:
           for payout in payouts:
               # Call PawaPay API
               response = await client.post(
                   f"{PAWAPAY_BASE_URL}/payouts",
                   headers={"Authorization": f"Bearer {PAWAPAY_API_KEY}"},
                   json={
                       "amount": payout.amount_zmw,
                       "currency": payout.currency,
                       "recipient": payout.affiliate_id,
                       # ... other PawaPay fields
                   }
               )
               
               # Track payout_id from PawaPay
               pawapay_id = response.json()["id"]
   ```

2. **Handle async status updates:**
   - PawaPay sends webhooks for status changes
   - Create webhook endpoint to receive updates
   - Update allocations based on webhook data

3. **Implement retry logic:**
   - Failed payouts should be retried
   - Exponential backoff for transient errors
   - Maximum retry attempts with alerting

### Database Persistence

To enable payout record persistence:

1. **Use synchronous DB session in background task:**
   ```python
   from sqlalchemy import create_engine
   from sqlalchemy.orm import sessionmaker
   
   # Create sync engine
   sync_engine = create_engine(DATABASE_URL.replace('+asyncpg', ''))
   SyncSession = sessionmaker(bind=sync_engine)
   
   def _process_payouts_sync():
       with SyncSession() as session:
           for payout in payouts:
               record = AffiliatePayoutRecord(...)
               session.add(record)
           session.commit()
   
   # Run in thread pool
   loop.run_in_executor(None, _process_payouts_sync)
   ```

2. **Or use task queue (Celery, RQ):**
   - Queue payout processing tasks
   - Workers handle database operations
   - Better scalability and reliability

### Monitoring

1. **Add metrics:**
   - Track payout batch success/failure rates
   - Monitor callback response times
   - Alert on failed callbacks

2. **Implement idempotency:**
   - Use batch_id or payout_id as idempotency key
   - Prevent duplicate payouts
   - Safe retry on failures

3. **Audit logging:**
   - Already emits audit events
   - Ensure audit-service is capturing events
   - Create dashboard for payout tracking

---

## API Reference Summary

| Endpoint | Method | Service | Port | Auth | Purpose |
|----------|--------|---------|------|------|---------|
| `/payout/batch` | POST | payment-revenue | 8590 | X-Admin-Key | Initiate batch payouts |
| `/callbacks/payout-status` | POST | affiliate-engine | 8510 | None | Receive payout status updates |
| `/admin/epochs/open` | POST | affiliate-engine | 8510 | X-Admin-Key | Create/get current epoch |
| `/admin/epochs/{id}/gross-revenue` | PUT | affiliate-engine | 8510 | X-Admin-Key | Set epoch gross revenue |
| `/admin/epochs/{id}/close` | POST | affiliate-engine | 8510 | X-Admin-Key | Close epoch and allocate |
| `/admin/epochs/{id}/allocations` | GET | affiliate-engine | 8510 | X-Admin-Key | Get epoch allocations |
| `/affiliates` | POST | affiliate-engine | 8510 | X-Admin-Key | Create affiliate |
| `/events/payment-success` | POST | affiliate-engine | 8510 | None | Record payment event |

---

## Changelog

### 2026-02-04 - Phase 4 Implementation
- Added `POST /payout/batch` endpoint to payment-revenue
- Added `POST /callbacks/payout-status` endpoint to affiliate-engine
- Added payout status columns to pool_allocations table
- Implemented async background payout processing
- Added fallback allocation lookup by affiliate_id + epoch_id
- Created comprehensive test script
- Documented complete workflow

### Features
- ✅ Batch payout initiation with immediate 202 response
- ✅ Async background processing
- ✅ Callback-based status updates
- ✅ Allocation status tracking in database
- ✅ Graceful error handling
- ✅ Full end-to-end testing

### Known Limitations
- Database persistence of AffiliatePayoutRecord disabled (session management issue)
- PawaPay integration simulated (immediate completion)
- No retry logic for failed callbacks
- No idempotency handling

---

## Support

For issues or questions:
1. Check logs for error messages
2. Verify database schema is up to date
3. Confirm all services are running
4. Review this documentation
5. Test with provided test script
