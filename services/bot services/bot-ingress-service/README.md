# Bot Ingress Service

This service consumes `incoming_messages` Redis stream, validates and enriches payloads (bot lookup, user lookup, capabilities), upserts/activates sessions and publishes enriched messages to `resolved_payload_default` or `resolved_payload_custom` streams.

Files of interest:
- `app/main.py` - FastAPI entrypoint with background listener
- `app/workers/queue_listener.py` - async Redis stream consumer
- `app/ingress/validator.py` - payload validation + idempotency
- `app/ingress/enricher.py` - enrichment orchestration (bot/auth/capabilities/session)
- `app/ingress/publisher.py` - writes enriched payload to lane-specific streams

Run locally (requires redis running):

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
