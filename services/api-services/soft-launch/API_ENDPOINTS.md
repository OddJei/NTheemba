# API Endpoints Documentation

## Order-Delivery Service (Port 8560)

### 1. Create Order
**Endpoint:** `POST /orders/create`

**Description:** Create a new order with optional affiliate metadata

**Headers:**
```
Authorization: Bearer {access_token}
X-Correlation-Id: {correlation_id} (optional)
```

**Request Body:**
```json
{
  "business_id": "a305ddb9-4432-4b7d-9e75-4225391f8bb4",
  "user_phone": "260973456789",
  "delivery_method": "pickup",
  "total_amount": 100000,
  "currency": "ZMW",
  "metadata": {
    "affiliate_id": "aff-xyz-789",
    "affiliate_code": "TESTCODE123"
  }
}
```

**Response (201 Created):**
```json
{
  "id": "68155958-785b-45bf-9c01-19193c44a949",
  "status": "pending_payment",
  "total_amount": 100000,
  "currency": "ZMW",
  "created_at": "2026-02-03T09:42:07.238Z"
}
```

**Notes:**
- `affiliate_id` and `affiliate_code` are optional but recommended for affiliate tracking
- `delivery_method` can be "pickup" or "delivery"
- Transaction fees are calculated based on business entitlements
- Creates `order_created` outbox event for affiliate attribution

---

### 2. Initiate Payment
**Endpoint:** `POST /orders/{order_id}/initiate_payment`

**Description:** Initiate a payment for an existing order via pawaPay

**Headers:**
```
Authorization: Bearer {access_token}
X-Correlation-Id: {correlation_id} (optional)
```

**Path Parameters:**
- `order_id`: UUID of the order

**Request Body:**
```json
{
  "phoneNumber": "260973456789",
  "provider": "MTN_MOMO_ZMB",
  "currency": "ZMW"
}
```

**Response (200 OK):**
```json
{
  "external_id": "13348ac2-1b23-4093-8c0e-b62a3cda9d6e",
  "status": "ACCEPTED",
  "amount_minor": 100000,
  "currency": "ZMW",
  "provider": "MTN_MOMO_ZMB",
  "phone_number": "260973456789"
}
```

**Notes:**
- Returns status `ACCEPTED` - payment processing happens asynchronously
- Calls payment-revenue service internally
- Order status changes to `pending_payment` after call

---

### 3. Mark Order as Paid (Internal)
**Endpoint:** `POST /orders/{order_id}/mark_paid`

**Description:** Internal endpoint called by payment-revenue when payment completes

**Headers:**
```
X-Correlation-Id: {correlation_id} (optional)
```

**Path Parameters:**
- `order_id`: UUID of the order

**Response (200 OK):**
```json
{
  "id": "68155958-785b-45bf-9c01-19193c44a949",
  "status": "paid",
  "total_amount": 100000
}
```

**Notes:**
- Service-to-service endpoint (auth bypassed for /orders/*/mark_paid pattern)
- Called automatically by payment-revenue after successful callback
- Changes order status from `pending_payment` to `paid`

---

### 4. Initiate Delivery
**Endpoint:** `POST /delivery/initiate/{order_id}`

**Description:** Generate delivery code and send notification to customer

**Headers:**
```
Authorization: Bearer {access_token}
X-Correlation-Id: {correlation_id} (optional)
```

**Path Parameters:**
- `order_id`: UUID of the order

**Response (201 Created):**
```json
{
  "id": "delivery-uuid",
  "order_id": "68155958-785b-45bf-9c01-19193c44a949",
  "status": "initiated",
  "delivery_code": "123456",
  "created_at": "2026-02-03T09:42:07.238Z"
}
```

**Notes:**
- Generates random 6-digit delivery code
- Sends notification to customer with delivery code
- Delivery code is hashed in database (salt + SHA256)

---

### 5. Confirm Delivery
**Endpoint:** `POST /delivery/{delivery_id}/confirm`

**Description:** Confirm delivery by code and emit affiliate attribution event

**Headers:**
```
Authorization: Bearer {access_token}
X-Correlation-Id: {correlation_id} (optional)
```

**Path Parameters:**
- `delivery_id`: UUID of the delivery record

**Request Body:**
```json
{
  "code": "123456"
}
```

**Response (200 OK):**
```json
{
  "id": "delivery-uuid",
  "order_id": "68155958-785b-45bf-9c01-19193c44a949",
  "status": "confirmed",
  "confirmed_by": "customer",
  "confirmed_at": "2026-02-03T09:42:07.238Z"
}
```

**Notes:**
- Code is verified against salted hash
- Creates `order_delivered` outbox event with affiliate metadata
- Emits order_delivered audit log
- Background dispatcher processes event to affiliate-engine

---

## Payment-Revenue Service (Port 8590)

### 1. Payment Callback (pawaPay)
**Endpoint:** `POST /callbacks/pawapay/deposits`

**Description:** Webhook endpoint for pawaPay payment completion notifications

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "depositId": "13348ac2-1b23-4093-8c0e-b62a3cda9d6e",
  "status": "COMPLETED",
  "amount": "1000.00",
  "currency": "ZMW"
}
```

**Response (200 OK):**
```json
{
  "status": "ok"
}
```

**Notes:**
- Called by pawaPay when payment is completed
- Automatically dispatches callback to order-delivery `/orders/{order_id}/mark_paid`
- Creates outbox events for downstream services
- Retries failed dispatch attempts with exponential backoff

---

## Affiliate-Engine Service (Port 8510)

### 1. Process Order Created Event
**Endpoint:** `POST /events/order-created`

**Description:** Process order creation event for affiliate attribution

**Headers:**
```
X-Correlation-Id: {correlation_id}
X-Idempotency-Key: {event_id}
Content-Type: application/json
```

**Request Body:**
```json
{
  "event_id": "order-created-68155958-785b-45bf-9c01-19193c44a949",
  "event_type": "order_created",
  "occurred_at": "2026-02-03T09:42:07.238Z",
  "correlation_id": "93e275f1-247f-484a-bd69-192744f63072",
  "producer": "order-delivery",
  "order_id": "68155958-785b-45bf-9c01-19193c44a949",
  "business_id": "a305ddb9-4432-4b7d-9e75-4225391f8bb4",
  "status": "pending_payment",
  "total_amount": 100000.0,
  "currency": "ZMW",
  "user_phone": "260973456789",
  "affiliate_code": "TESTCODE123",
  "affiliate_id": "aff-xyz-789"
}
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "attributed": true,
  "attribution_id": "44052cf0-e284-4837-bc02-2cf4e58a7dd7"
}
```

**Notes:**
- Can attribute using either `affiliate_code` OR `affiliate_id`
- Creates AffiliateAttribution record in database
- Idempotency key ensures duplicate events don't create multiple attributions
- Emits audit log for tracking

---

### 2. Process Order Delivered Event
**Endpoint:** `POST /events/order/delivered`

**Description:** Process order delivery completion for final attribution confirmation

**Headers:**
```
X-Correlation-Id: {correlation_id}
X-Idempotency-Key: {event_id}
Content-Type: application/json
```

**Request Body:**
```json
{
  "event_id": "order-delivered-68155958-785b-45bf-9c01-19193c44a949",
  "event_type": "order_delivered",
  "occurred_at": "2026-02-03T09:42:07.238Z",
  "correlation_id": "93e275f1-247f-484a-bd69-192744f63072",
  "producer": "order-delivery",
  "order_id": "68155958-785b-45bf-9c01-19193c44a949",
  "business_id": "a305ddb9-4432-4b7d-9e75-4225391f8bb4",
  "status": "delivered",
  "total_amount": 100000.0,
  "currency": "ZMW",
  "user_phone": "260973456789",
  "affiliate_code": "TESTCODE123",
  "affiliate_id": "aff-xyz-789"
}
```

**Response (200 OK):**
```json
{
  "status": "ok"
}
```

**Notes:**
- Called after delivery is confirmed
- Updates attribution status
- Emits audit log for delivery completion
- Background dispatcher automatically calls this from outbox events

---

## End-to-End Flow Example

```
1. User/App creates order
   POST /orders/create
   ↓
   Order created with status: pending_payment
   order_created event → outbox → background dispatcher → affiliate-engine

2. User initiates payment
   POST /orders/{order_id}/initiate_payment
   ↓
   Payment-revenue receives request
   pawaPay deposit initiated (ACCEPTED status returned)

3. Payment completes (async)
   pawaPay webhook: POST /callbacks/pawapay/deposits
   ↓
   Payment-revenue calls order-delivery: POST /orders/{order_id}/mark_paid
   ↓
   Order status changes to: paid

4. Delivery initiated
   POST /delivery/initiate/{order_id}
   ↓
   Delivery code generated (6 digits)
   Notification sent to customer

5. Delivery confirmed by customer
   POST /delivery/{delivery_id}/confirm
   ↓
   Code verified, order_delivered event created → outbox
   Background dispatcher processes → affiliate-engine

6. Affiliate attribution finalized
   Affiliate-engine receives order_delivered event
   Attribution status updated: "attributed"
   Audit logs emitted to audit-service
```

---

## Background Processing

### Outbox Dispatcher
- **Service:** order-delivery
- **Interval:** 2 seconds (configurable via `OUTBOX_DISPATCH_INTERVAL_SECONDS`)
- **Batch Size:** 50 events (configurable via `OUTBOX_DISPATCH_BATCH_SIZE`)
- **Function:** Processes unprocessed outbox events and dispatches them to affiliate-engine

### Enabled:** Default true (set `OUTBOX_DISPATCH_ENABLED=false` to disable)

---

## Authentication

### Access Tokens
- Issued by: msme-engine (`POST /auth/login`)
- Format: JWT Bearer token
- Used for: All user-facing endpoints
- Created from: `identifier` (username) + `password`

**Example:**
```bash
curl -X POST http://127.0.0.1:8500/auth/login \
  -H "Content-Type: application/json" \
  -d '{"identifier": "msme_service", "password": "S3rv!c3-P@ssw0rd"}'
```

### Service-to-Service
- Some endpoints (like `/orders/{id}/mark_paid`) skip authentication
- Pattern-based auth bypass for internal service calls
- No additional headers needed for internal endpoints

---

## Error Handling

### Common Status Codes
- `200 OK`: Success
- `201 Created`: Resource created
- `400 Bad Request`: Invalid input
- `401 Unauthorized`: Missing/invalid auth token
- `422 Unprocessable Entity`: Validation error (missing required fields)
- `500 Internal Server Error`: Server error

### Error Response Format
```json
{
  "detail": "Error message or validation details"
}
```

---

## Testing

### Run Full E2E Test
```bash
cd /path/to/soft-launch
python scripts/test_e2e_affiliate_id.py
```

**What it tests:**
1. Order creation with affiliate_id
2. Payment initiation
3. Payment callback simulation
4. Order status update to paid
5. Affiliate attribution creation

---

## Configuration Environment Variables

### Order-Delivery
- `DATABASE_URL`: PostgreSQL connection string
- `PG_SCHEMA`: Database schema (order_delivery)
- `MSME_BASE_URL`: MSME engine URL (default: http://127.0.0.1:8500)
- `PAYMENT_REVENUE_BASE_URL`: Payment service URL (default: http://127.0.0.1:8590)
- `AFFILIATE_ENGINE_BASE_URL`: Affiliate service URL (default: http://127.0.0.1:8510)
- `AUDIT_SERVICE_URL`: Audit service URL (default: http://127.0.0.1:8290)
- `OUTBOX_DISPATCH_ENABLED`: Enable background dispatcher (default: true)
- `OUTBOX_DISPATCH_INTERVAL_SECONDS`: Polling interval (default: 2.0)
- `OUTBOX_DISPATCH_BATCH_SIZE`: Events per batch (default: 50)

### Affiliate-Engine
- `DATABASE_URL`: PostgreSQL connection string
- `PG_SCHEMA`: Database schema (affiliate_engine)
- `MSME_BASE_URL`: MSME engine URL
- `AUDIT_SERVICE_URL`: Audit service URL
- `AUDIT_EMIT_ENABLED`: Enable audit logging (default: true)
- `AUDIT_FORWARD_LOGS_ENABLED`: Forward service logs to audit (default: true)
- `AUDIT_FORWARD_LOGS_LEVEL`: Log level (default: INFO)

---

## Support

For issues or questions, refer to the service logs:
```bash
docker logs soft-launch-order-delivery-1
docker logs soft-launch-payment-revenue-1
docker logs soft-launch-affiliate-engine-1
```
