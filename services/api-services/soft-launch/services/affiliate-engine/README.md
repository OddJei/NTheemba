# Affiliate Engine (Soft Launch)

This is the **soft-launch** Affiliate Engine implementation.

It lives under `api-services/soft-launch/services/affiliate-engine/src/` to avoid duplication.

## Run (local)

```powershell
Set-Location api-services/soft-launch/services/affiliate-engine
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn src.app.main:app --reload --port 8510 --host 127.0.0.1
```

## Environment

- `DATABASE_URL` (optional)
  - default: `sqlite+aiosqlite:///./affiliate_engine.db`

- `EVENT_SINK_URL` (optional, for outbox dispatch)
  - When set, you can run the outbox dispatcher to push `affiliate_events` to an external event sink.
  - Example: `http://localhost:9000/events`

- `AUDIT_SERVICE_URL` (optional)
  - default: `http://127.0.0.1:8290`

- `AUDIT_EMIT_ENABLED` (optional)
  - default: `true`
  - Set to `false` to disable emitting audit events.

- `AUDIT_FORWARD_LOGS_ENABLED` (optional)
  - default: `true`
  - When enabled, forwards Python logs (WARNING+) to Audit Service as `event_type=python_log`.

- `AUDIT_FORWARD_LOGS_LEVEL` (optional)
  - default: `WARNING`
  - Minimum log level to forward (e.g. `ERROR`).

- `AUDIT_FORWARD_LOGS_EXCLUDE` (optional)
  - default: `audit_client,httpx,httpcore,asyncio`

- Audit Service (optional)
  - The service emits best-effort audit events (non-blocking) for key actions like affiliate creation, link creation, and click tracking.
  - `AUDIT_SERVICE_URL` (optional)
    - default: `http://127.0.0.1:8290`
  - `AUDIT_EMIT_ENABLED` (optional)
    - default: `true` (set to `0`/`false` to disable)
  - `AUDIT_TIMEOUT_SECONDS` (optional)
    - default: `3.0`

## API (minimal)

- `POST /affiliates`
- `GET /affiliates`
- `GET /affiliates/{affiliate_id}`
- `POST /affiliates/{affiliate_id}/links`
- `GET /affiliates/{affiliate_id}/links`
- `POST /track/click`
- `POST /attribute/order`
- `GET /events/affiliate/{affiliate_id}`
- `GET /affiliates/{affiliate_id}/clicks`
- `GET /affiliates/{affiliate_id}/attributions`
- `POST /events/payment-success`
- `POST /events/order-created`
- `GET /affiliates/{affiliate_id}/earnings`
- `GET /affiliates/{affiliate_id}/earnings/records`
- `GET /affiliates/{affiliate_id}/dashboard?days=30`

Notes:
- `POST /track/click` and `POST /attribute/order` require a producer-supplied `event_id` in the JSON payload.
- Pool scoring uses the append-only `affiliate_events` log (no backfill).

## Headers

- `X-Correlation-Id` (required by contract; echoed back in responses)
- `X-Idempotency-Key` (recommended for write endpoints)

## Outbox dispatcher (optional)

The Affiliate Engine writes an append-only `affiliate_events` log for clicks, conversions, and sales.
If you want downstream systems (e.g., notifications, analytics, a dashboard service) to receive these events automatically:

```powershell
Set-Location api-services/soft-launch/services/affiliate-engine
Set-Item -Path Env:EVENT_SINK_URL -Value "http://localhost:9000/events"
python -m src.app.outbox_dispatcher
```

Notes:
- Events are dispatched once and then marked with `dispatched_at`.
