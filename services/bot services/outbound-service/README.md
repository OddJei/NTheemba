# Outbound Service

Consumes `outbound:requests` from Redis Streams and delivers provider payloads to external providers.

## Run locally

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt
uvicorn app.main:app --reload --port 8010
```

## Demo (publish + read receipts)

With the service running on `http://127.0.0.1:8010`, run:

```powershell
python scripts\demo_outbound_http.py
```

This publishes a message to `outbound:requests`, then prints receipts from `outbound:http`.

## Redis contracts

  - `event_id`, `session_id`, `provider`, `provider_payload`, `callback_url?`, `trace_id?`, `attempts?`


