# Notification Service - Queue-Based Architecture

## Overview

The notification service has been refactored to use a **queue-based, asynchronous architecture**. All `/send` endpoints now:

1. **Persist notifications** to queue immediately (status: `pending`)
2. **Return success response** to caller without waiting for delivery
3. **Background worker** processes queue and sends through gateways every 10 seconds

This decouples API responsiveness from external gateway latency and enables **automatic retries with exponential backoff**.

## Architecture

```
Request to /send
        ↓
Validate payload
        ↓
Persist to queue (status: pending)
        ↓
Return 201 + notification record (immediate)
        ↓
Background Worker (every 10s)
        ├─ Find pending/retry_pending notifications
        ├─ Send via Email/SMS/In-App gateway
        ├─ Mark as 'sent' on success
        └─ Mark as 'retry_pending' or 'failed' on error
```

## Endpoint Contracts (UNCHANGED)

### POST /notification/send
Persist a notification to queue.

**Request:**
```json
{
  "user_id": "user123",
  "business_id": "biz456",
  "channel": "email" | "sms" | "in_app",
  "template": "optional_template_name",
  "payload": {
    "to": "recipient@example.com",
    "subject": "Email Subject",
    "message": "Message body",
    "html": "optional_html_body"
  }
}
```

**Response (201):**
```json
{
  "id": "ntf_a1b2c3d4e5f6g7h8i9j0",
  "user_id": "user123",
  "business_id": "biz456",
  "channel": "email",
  "template": null,
  "payload": { ... },
  "status": "pending",
  "error_message": null,
  "retry_count": 0,
  "created_at": "2026-01-31T13:45:00.000Z",
  "sent_at": null,
  "failed_at": null,
  "next_retry_at": null
}
```

### POST /notify/email
Queue an email notification.

**Request:**
```json
{
  "to": "recipient@example.com",
  "subject": "Email Subject",
  "message": "Message body",
  "html": "optional_html_body",
  "user_id": "optional_user123",
  "business_id": "optional_biz456",
  "template": "optional_template_name"
}
```

**Response (201):**
```json
{
  "ok": true,
  "id": "ntf_a1b2c3d4e5f6g7h8i9j0",
  "status": "pending",
  "message": "Email queued"
}
```

### POST /notify/sms
Queue an SMS notification.

**Request:**
```json
{
  "to": "optional_single_recipient",
  "recipients": ["recipient1", "recipient2"],
  "message": "SMS message text",
  "user_id": "optional_user123",
  "business_id": "optional_biz456",
  "template": "optional_template_name"
}
```

**Response (201):**
```json
{
  "ok": true,
  "id": "ntf_a1b2c3d4e5f6g7h8i9j0",
  "status": "pending",
  "message": "SMS queued"
}
```

## Notification Statuses

| Status | Meaning | Next Action |
|--------|---------|-------------|
| `pending` | Queued, never attempted | Worker will try to send |
| `retry_pending` | Failed, scheduled for retry | Worker will retry at `next_retry_at` |
| `sent` | Successfully delivered | Persisted for audit trail (no further action) |
| `failed` | Failed after max retries (3x) | Manual intervention may be needed |

## Query Notification Status

### GET /notification/:id
Get single notification record.

**Response:**
```json
{
  "id": "ntf_a1b2c3d4e5f6g7h8i9j0",
  "user_id": "user123",
  "business_id": "biz456",
  "channel": "email",
  "template": null,
  "payload": { ... },
  "status": "sent",
  "error_message": null,
  "retry_count": 1,
  "created_at": "2026-01-31T13:45:00.000Z",
  "sent_at": "2026-01-31T13:45:05.000Z",
  "failed_at": null,
  "next_retry_at": null
}
```

### GET /notification/user/:user_id
List all notifications for a user (sorted by most recent first).

**Response:**
```json
[
  { "id": "ntf_...", "status": "sent", ... },
  { "id": "ntf_...", "status": "pending", ... }
]
```

## Retry Logic

- **Max retries:** 3 attempts
- **Backoff formula:** `5s * 2^(retry_count)` = 5s, 10s, 20s
- **Retry timeline:**
  - Attempt 1: Immediately (pending → retry_pending)
  - Attempt 2: After ~5 seconds
  - Attempt 3: After ~10 seconds
  - Attempt 4: After ~20 seconds
  - After 4th failure: Marked as `failed` (no more retries)

## Background Worker

**File:** `workers/notificationWorker.js`

**Behavior:**
- Starts automatically when service initializes
- Wakes every 10 seconds to flush pending notifications
- Processes all `pending` and ready `retry_pending` notifications in parallel
- Updates status and retry metadata in persistent storage
- Logs all send attempts (success/failure)

**Configuration:**
```javascript
const RETRY_BACKOFF_MS = 5000;      // Base backoff
const MAX_RETRIES = 3;              // Max attempts
const WORKER_INTERVAL_MS = 10000;   // Check queue every 10s
```

## Benefits of Queue-Based Architecture

✅ **API Responsiveness:** Endpoints return immediately (no gateway latency)

✅ **Automatic Retries:** Exponential backoff handles transient failures

✅ **Audit Trail:** All notifications persisted, queryable by user/status

✅ **Scalability:** Worker can be spawned on separate threads/processes

✅ **Fault Tolerance:** Service restart doesn't lose queued notifications

✅ **Contract Preservation:** Existing API signatures unchanged; only behavior differs

## Example: Sending an Email

### Step 1: Client calls POST /notification/send
```bash
curl -X POST http://localhost:8570/notification/send \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "channel": "email",
    "payload": {
      "to": "test@example.com",
      "subject": "Welcome!",
      "message": "Hello, welcome to our service."
    }
  }'
```

**Response (201, immediate):**
```json
{
  "id": "ntf_a1b2c3d4e5f6g7h8i9j0",
  "status": "pending",
  "created_at": "2026-01-31T13:45:00.000Z"
}
```

### Step 2: Background Worker Processes (after ~2 seconds)
- Worker finds notification with status `pending`
- Calls `emailService.sendEmail()`
- If success: Sets status → `sent`, sent_at → now
- If failure: Sets status → `retry_pending`, next_retry_at → (now + 5s)

### Step 3: Retry Handling
- Worker retries at scheduled times with exponential backoff
- After 3 failed attempts: status → `failed`, persisted forever for audit

### Step 4: Client Queries Status
```bash
curl http://localhost:8570/notification/ntf_a1b2c3d4e5f6g7h8i9j0
```

Response shows final status (`sent` or `failed`) and delivery timestamp.

## Testing the Queue

### 1. Send a Notification
```bash
curl -X POST http://localhost:8570/notification/send \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "channel": "email",
    "payload": {
      "to": "test@example.com",
      "subject": "Test",
      "message": "Test message"
    }
  }'
```

### 2. Wait ~10 seconds for worker to process

### 3. Query the notification
```bash
curl http://localhost:8570/notification/ntf_<id>
```

You should see status updated to `sent` (assuming email delivery succeeded).

## Persistent Storage

Notifications are stored in: `./dev_notifications.json` (dev) or path specified by `NOTIFICATION_DB_FILE` env var.

**Storage format:**
```json
{
  "notifications": [
    {
      "id": "ntf_...",
      "user_id": "...",
      "business_id": "...",
      "channel": "email|sms|in_app",
      "template": null,
      "payload": { ... },
      "status": "pending|sent|failed|retry_pending",
      "error_message": null,
      "retry_count": 0,
      "created_at": "...",
      "sent_at": null,
      "failed_at": null,
      "next_retry_at": null
    }
  ]
}
```

## Logging

The worker logs all activity to stdout/stderr:

```
Starting notification worker...
Processing 3 pending notifications
Notification ntf_a1b2c3d4e5f6g7h8i9j0 sent successfully
Notification ntf_b2c3d4e5f6g7h8i9j0k1 will retry (attempt 1)
Notification ntf_c3d4e5f6g7h8i9j0k1l2 failed after 3 retries
```

## Migration Notes

- **Backward Compatible:** API contracts unchanged (same request/response format)
- **Behavior Change:** Responses return immediately instead of blocking on send
- **Status Field Change:** `created` → `pending`, new fields: `retry_count`, `failed_at`, `next_retry_at`
- **Old Status:** `sent` status still exists, indicates successful delivery
- **Old Status:** `failed` status now means "failed after max retries" not "immediate failure"

## Future Enhancements

- [ ] Move to PostgreSQL table (instead of JSON file) for multi-instance deployments
- [ ] Webhook callbacks on notification delivery status
- [ ] Template rendering for batch notifications
- [ ] Rate limiting per user/business
- [ ] Dead-letter queue for permanently failed notifications
- [ ] Notification preferences (do not disturb hours, channel preferences, etc.)
