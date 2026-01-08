# Soft-launch Notification Service (Node)

This service fuses the JS `notifier` gateway behavior into a single soft-launch service.

## Endpoints

- `GET /health` -> `{ "status": "ok" }`
- `POST /notify/sms` -> `{ to|recipients, message }`
- `POST /notify/email` -> `{ to, subject, message?, html? }`

Python-compatible API (mirrors the old FastAPI notification-service routes):
- `POST /notification/send`
- `GET /notification/:id`
- `GET /notification/user/:user_id`

## Configuration

Copy `.env.example` to `.env` and set values.

### SMS via TextBee

Set:
- `SMS_PROVIDER=textbee`
- `TEXTBEE_API_KEY=...`
- `TEXTBEE_DEVICE_ID=...`

The adapter calls:
`POST https://api.textbee.dev/api/v1/gateway/devices/{DEVICE_ID}/send-sms`
with header `x-api-key`.

## Run locally

```powershell
cd "C:\Users\SMART PC\Documents\NTheemba\services\api-services\soft-launch\services\notification"
npm install
npm run dev
```

Default: `http://127.0.0.1:8561`

## Storage

A simple JSON file store is used for soft-launch:
- `NOTIFICATION_DB_FILE` (default `./dev_notifications.json`)

This keeps the service self-contained (no Postgres/Redis required).
