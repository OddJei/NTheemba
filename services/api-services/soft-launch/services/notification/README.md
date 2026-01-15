# Soft-launch Notification Service (Node)

This service fuses the JS notifier gateway behavior into a single soft-launch service.

Base URL (default): `http://127.0.0.1:8570`

## HTTP API

### Health / info

- `GET /`
	- Response: `{ "ok": true, "service": "softlaunch-notification" }`

- `GET /health`
	- Response: `{ "status": "ok" }`

- `GET /notify/ping`
	- Response: `{ "ok": true, "service": "softlaunch-notification" }`

### Gateway-style endpoints (from notifier)

These mirror the original gateway behavior.

- `POST /notify/email`
	- Body:
		- `to` (string) required
		- `subject` (string) required
		- `message` (string) optional (plain text)
		- `html` (string) optional
		- At least one of `message` or `html` is required.
	- Success: `200` -> `{ "ok": true, "message": "Email sent" }`
	- Errors:
		- `400` -> `{ "ok": false, "error": "missing to/subject/message" }`
		- `500` -> `{ "ok": false, "error": "email_failed" }`

Example:

```bash
curl -s -X POST http://127.0.0.1:8570/notify/email \
	-H "Content-Type: application/json" \
	-d '{"to":"user@example.com","subject":"Hello","message":"Hi there"}'
```

- `POST /notify/sms`
	- Body:
		- `message` (string) required
		- `to` (string) OR `recipients` (array of strings)
	- Success: `200` -> `{ "ok": true, "result": ... }`
	- Errors:
		- `400` -> `{ "ok": false, "error": "missing to/message" }`
		- `500` -> `{ "ok": false, "error": "sms_failed" }`

Example:

```bash
curl -s -X POST http://127.0.0.1:8570/notify/sms \
	-H "Content-Type: application/json" \
	-d '{"to":"+15551234567","message":"Test SMS"}'
```

### Notification-service-style endpoints (Python-compatible shape)

These mimic the old FastAPI notification-service route shapes, but the payload is simplified.

- `POST /notification/send`
	- Body:
		- `channel` (string) required: `"sms"`, `"email"`, or `"in_app"`
		- `user_id` (string) optional
		- `business_id` (string) optional
		- `template` (string) optional
		- `payload` (object) optional
			- For `channel=sms`:
				- `to` (string) OR `recipients` (array)
				- `message` (string)
			- For `channel=email`:
				- `to` (string)
				- `subject` (string)
				- `message` (string) optional
				- `html` (string) optional
			- For `channel=in_app`:
				- Any `payload` is accepted and will be stored only (no external delivery)
	- Response: `201` -> notification record (even if delivery fails; see `status`)
		- `status` is `"sent"` or `"failed"`
		- `error_message` contains the failure reason when `failed`
	- Errors:
		- `400` if `channel` is missing/unsupported

Example (SMS):

```bash
curl -s -X POST http://127.0.0.1:8570/notification/send \
	-H "Content-Type: application/json" \
	-d '{"user_id":"u_1","channel":"sms","payload":{"to":"+15551234567","message":"Hello"}}'
```

Example (email):

```bash
curl -s -X POST http://127.0.0.1:8570/notification/send \
	-H "Content-Type: application/json" \
	-d '{"user_id":"u_1","channel":"email","payload":{"to":"user@example.com","subject":"Hello","message":"Hi"}}'
```

- `GET /notification/:id`
	- Success: `200` -> notification record
	- Not found: `404` -> `{ "detail": "notification not found" }`

- `GET /notification/user/:user_id`
	- Success: `200` -> `[ ...notification records... ]`
	- Sorted newest-first by `created_at`.

## Notification record shape

```json
{
	"id": "ntf_...",
	"user_id": "u_1",
	"business_id": null,
	"channel": "sms",
	"template": null,
	"payload": {"to":"+15551234567","message":"Hello"},
	"status": "sent",
	"error_message": null,
	"created_at": "2026-01-08T00:00:00.000Z",
	"sent_at": "2026-01-08T00:00:01.000Z"
}
```

## Configuration

Copy `.env.example` to `.env` and set values.

Common env vars:

- `HOST` (default `127.0.0.1`)
- `PORT` (default `8561`)
- `NOTIFICATION_DB_FILE` (default `./dev_notifications.json`)

### Email

- `SMTP_JSON=1` (recommended for local/dev): email is not sent; it is generated via nodemailer JSON transport.
- For real SMTP, set `EMAIL_SMTP_HOST`, `EMAIL_SMTP_PORT`, `MAIL_USER`, `MAIL_PASS`, and optionally `EMAIL_FROM`.

### SMS via TextBee

Set:

- `SMS_PROVIDER=textbee`
- `TEXTBEE_API_KEY=...`
- `TEXTBEE_DEVICE_ID=...`
- Optional: `TEXTBEE_BASE_URL=https://api.textbee.dev/api/v1`

The adapter calls:
`POST https://api.textbee.dev/api/v1/gateway/devices/{DEVICE_ID}/send-sms`
with header `x-api-key`.

## Run locally

```powershell
cd "C:\Users\SMART PC\Documents\NTheemba\services\api-services\soft-launch\services\notification"
npm ci
npm start
```

Default: `http://127.0.0.1:8561`

## Storage

A simple JSON file store is used for soft-launch (no Postgres/Redis required).
