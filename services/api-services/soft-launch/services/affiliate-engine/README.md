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
