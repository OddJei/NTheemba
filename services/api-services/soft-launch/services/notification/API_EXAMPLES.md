# Notification Service API Examples

## Queue-Based Architecture Examples

### 1. Send Email Notification

**Endpoint:** `POST /notification/send`

```bash
curl -X POST http://localhost:8570/notification/send \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "business_id": "biz_456",
    "channel": "email",
    "template": "welcome_email",
    "payload": {
      "to": "customer@example.com",
      "subject": "Welcome to NTheemba!",
      "message": "Thank you for signing up.",
      "html": "<h1>Welcome</h1><p>Thank you for signing up.</p>"
    }
  }'
```

**Response (201 - Queued):**
```json
{
  "id": "ntf_8f7e6d5c4b3a2a1a0f9e",
  "user_id": "user_123",
  "business_id": "biz_456",
  "channel": "email",
  "template": "welcome_email",
  "payload": {
    "to": "customer@example.com",
    "subject": "Welcome to NTheemba!",
    "message": "Thank you for signing up.",
    "html": "<h1>Welcome</h1><p>Thank you for signing up.</p>"
  },
  "status": "pending",
  "error_message": null,
  "retry_count": 0,
  "created_at": "2026-01-31T14:00:00.000Z",
  "sent_at": null,
  "failed_at": null,
  "next_retry_at": null
}
```

### 2. Send SMS Notification via /notify/sms

**Endpoint:** `POST /notify/sms`

```bash
curl -X POST http://localhost:8570/notify/sms \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+234803456789",
    "message": "Your OTP is: 123456",
    "user_id": "user_789",
    "business_id": "biz_456"
  }'
```

**Response (201 - Queued):**
```json
{
  "ok": true,
  "id": "ntf_a1b2c3d4e5f6g7h8i9j0",
  "status": "pending",
  "message": "SMS queued"
}
```

### 3. Send SMS to Multiple Recipients

**Endpoint:** `POST /notify/sms`

```bash
curl -X POST http://localhost:8570/notify/sms \
  -H "Content-Type: application/json" \
  -d '{
    "recipients": ["+234803456789", "+234702345678", "+234601234567"],
    "message": "Breaking news: System maintenance scheduled for tonight.",
    "business_id": "biz_news_org"
  }'
```

**Response (201 - Queued):**
```json
{
  "ok": true,
  "id": "ntf_b2c3d4e5f6g7h8i9j0k1",
  "status": "pending",
  "message": "SMS queued"
}
```

### 4. Send Email via /notify/email

**Endpoint:** `POST /notify/email`

```bash
curl -X POST http://localhost:8570/notify/email \
  -H "Content-Type: application/json" \
  -d '{
    "to": "manager@business.com",
    "subject": "Monthly Sales Report",
    "message": "Please find attached your monthly sales report.",
    "html": "<h2>Monthly Sales Report</h2><p>Please find attached your monthly sales report for review.</p>",
    "user_id": "manager_001",
    "business_id": "biz_retail_001"
  }'
```

**Response (201 - Queued):**
```json
{
  "ok": true,
  "id": "ntf_c3d4e5f6g7h8i9j0k1l2",
  "status": "pending",
  "message": "Email queued"
}
```

### 5. Check Notification Status

**Endpoint:** `GET /notification/:id`

```bash
# Check status of notification queued above
curl http://localhost:8570/notification/ntf_8f7e6d5c4b3a2a1a0f9e
```

**Response (After worker processes - Status: Sent):**
```json
{
  "id": "ntf_8f7e6d5c4b3a2a1a0f9e",
  "user_id": "user_123",
  "business_id": "biz_456",
  "channel": "email",
  "template": "welcome_email",
  "payload": {
    "to": "customer@example.com",
    "subject": "Welcome to NTheemba!",
    "message": "Thank you for signing up.",
    "html": "<h1>Welcome</h1><p>Thank you for signing up.</p>"
  },
  "status": "sent",
  "error_message": null,
  "retry_count": 0,
  "created_at": "2026-01-31T14:00:00.000Z",
  "sent_at": "2026-01-31T14:00:05.000Z",
  "failed_at": null,
  "next_retry_at": null
}
```

**Response (If temporary failure - Status: Retry Pending):**
```json
{
  "id": "ntf_8f7e6d5c4b3a2a1a0f9e",
  "user_id": "user_123",
  "business_id": "biz_456",
  "channel": "email",
  "template": "welcome_email",
  "payload": { ... },
  "status": "retry_pending",
  "error_message": "ECONNREFUSED: Connection refused to SMTP server",
  "retry_count": 1,
  "created_at": "2026-01-31T14:00:00.000Z",
  "sent_at": null,
  "failed_at": null,
  "next_retry_at": "2026-01-31T14:00:05.000Z"
}
```

**Response (After max retries - Status: Failed):**
```json
{
  "id": "ntf_8f7e6d5c4b3a2a1a0f9e",
  "user_id": "user_123",
  "business_id": "biz_456",
  "channel": "email",
  "template": "welcome_email",
  "payload": { ... },
  "status": "failed",
  "error_message": "ECONNREFUSED: Connection refused to SMTP server",
  "retry_count": 3,
  "created_at": "2026-01-31T14:00:00.000Z",
  "sent_at": null,
  "failed_at": "2026-01-31T14:00:25.000Z",
  "next_retry_at": null
}
```

### 6. List User's Notifications

**Endpoint:** `GET /notification/user/:user_id`

```bash
curl http://localhost:8570/notification/user/user_123
```

**Response:**
```json
[
  {
    "id": "ntf_8f7e6d5c4b3a2a1a0f9e",
    "user_id": "user_123",
    "business_id": "biz_456",
    "channel": "email",
    "template": "welcome_email",
    "payload": { ... },
    "status": "sent",
    "error_message": null,
    "retry_count": 0,
    "created_at": "2026-01-31T14:00:00.000Z",
    "sent_at": "2026-01-31T14:00:05.000Z",
    "failed_at": null,
    "next_retry_at": null
  },
  {
    "id": "ntf_9g8h7i6j5k4l3m2n1o0p",
    "user_id": "user_123",
    "business_id": "biz_456",
    "channel": "sms",
    "template": null,
    "payload": { ... },
    "status": "pending",
    "error_message": null,
    "retry_count": 0,
    "created_at": "2026-01-31T14:05:00.000Z",
    "sent_at": null,
    "failed_at": null,
    "next_retry_at": null
  }
]
```

## In-App Notifications

**Endpoint:** `POST /notification/send`

```bash
curl -X POST http://localhost:8570/notification/send \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_999",
    "business_id": "biz_999",
    "channel": "in_app",
    "template": "order_status_update",
    "payload": {
      "title": "Order Shipped",
      "message": "Your order #12345 has been shipped",
      "action_url": "https://app.ntheemba.com/orders/12345",
      "icon": "📦"
    }
  }'
```

**Response (201):**
```json
{
  "id": "ntf_x1x2x3x4x5x6x7x8x9x0",
  "user_id": "user_999",
  "business_id": "biz_999",
  "channel": "in_app",
  "template": "order_status_update",
  "payload": {
    "title": "Order Shipped",
    "message": "Your order #12345 has been shipped",
    "action_url": "https://app.ntheemba.com/orders/12345",
    "icon": "📦"
  },
  "status": "sent",
  "error_message": null,
  "retry_count": 0,
  "created_at": "2026-01-31T14:10:00.000Z",
  "sent_at": "2026-01-31T14:10:00.100Z",
  "failed_at": null,
  "next_retry_at": null
}
```

*Note: In-app notifications are marked as `sent` immediately since they don't require external gateway delivery.*

## Common Workflows

### Workflow 1: Send Confirmation Email After Payment

```bash
# Step 1: Queue confirmation email
NOTIF_ID=$(curl -s -X POST http://localhost:8570/notification/send \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "business_id": "biz_456",
    "channel": "email",
    "payload": {
      "to": "user@example.com",
      "subject": "Payment Confirmed",
      "message": "Your payment has been received. Reference: TXN123456"
    }
  }' | jq -r '.id')

echo "Email queued with ID: $NOTIF_ID"

# Step 2: Wait 2-10 seconds for worker to process

# Step 3: Check delivery status
curl http://localhost:8570/notification/$NOTIF_ID | jq '.status'
```

### Workflow 2: Send SMS to Multiple Users

```bash
# Queue SMS notifications for multiple users
for PHONE in "+234803456789" "+234702345678" "+234601234567"; do
  curl -X POST http://localhost:8570/notify/sms \
    -H "Content-Type: application/json" \
    -d "{
      \"to\": \"$PHONE\",
      \"message\": \"Special offer: 20% off all items this weekend!\"
    }"
done
```

### Workflow 3: Monitor Notification Delivery

```bash
# Get all notifications for a user
curl http://localhost:8570/notification/user/user_123 | jq '.[] | {id, status, created_at, sent_at}'

# Filter by status
curl http://localhost:8570/notification/user/user_123 | jq '.[] | select(.status=="failed")'

# Count by status
curl http://localhost:8570/notification/user/user_123 | jq 'group_by(.status) | map({status: .[0].status, count: length})'
```

## Error Scenarios

### Invalid Channel

```bash
curl -X POST http://localhost:8570/notification/send \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "channel": "telegram",
    "payload": {}
  }'
```

**Response (400):**
```json
{
  "detail": "unsupported channel"
}
```

### Missing Email Subject

```bash
curl -X POST http://localhost:8570/notify/email \
  -H "Content-Type: application/json" \
  -d '{
    "to": "user@example.com",
    "message": "Missing subject!"
  }'
```

**Response (400):**
```json
{
  "ok": false,
  "error": "missing to/subject/message"
}
```

### Missing SMS Recipient

```bash
curl -X POST http://localhost:8570/notify/sms \
  -H "Content-Type: application/json" \
  -d '{
    "message": "No recipient specified!"
  }'
```

**Response (400):**
```json
{
  "ok": false,
  "error": "missing to/message"
}
```

## Testing Retry Logic

### Simulate Email Gateway Failure

1. **Stop email service** or disconnect network
2. **Queue notification:**
   ```bash
   curl -X POST http://localhost:8570/notify/email \
     -H "Content-Type: application/json" \
     -d '{
       "to": "test@example.com",
       "subject": "Test",
       "message": "Retry test"
     }'
   ```
3. **Check status immediately:** Should be `pending`
4. **Check after 10 seconds:** Should be `retry_pending` with `next_retry_at`
5. **Re-enable email service**
6. **Check after next interval:** Should eventually become `sent`

## Performance Notes

- **Queue time:** <10ms
- **Worker processing:** Every 10 seconds
- **Email delivery:** Depends on SMTP server (typically 100-500ms)
- **SMS delivery:** Depends on TextBee API (typically 200-1000ms)
- **In-app delivery:** <1ms (no external service)

---

For more details, see [QUEUE_ARCHITECTURE.md](QUEUE_ARCHITECTURE.md) and [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md)
