# Bot Ingress Service

This service consumes the `ingress:incoming` Redis stream, validates and enriches payloads (bot lookup, user lookup, capabilities), and publishes a canonical enriched envelope to:

- Audit/replay: `ingress:resolved_payload`
- Bot lane: `bot:lane:{bot_type}` (e.g. `bot:lane:default`, `bot:lane:custom`)

## Cache-first enrichment

Ingress is designed to be **cache-first**. It uses Redis to cache:

- Bot lookup by phone (`to`)
- User lookup by phone (`from`) (+ optional `business_id` for custom bots)
- Capabilities by mode
- Optional `session_context` for the session

On cache miss, Ingress will call the upstream service (Bot/Auth/Capability). For `session_context`, Ingress can optionally call ICE to preload and return context, then cache it for the session.

### Environment variables

- `INGRESS_CACHE_ENABLED` (default `True`)
- `INGRESS_BOT_CACHE_TTL` (default `3600`)
- `INGRESS_USER_CACHE_TTL` (default `900`)
- `INGRESS_CAPABILITIES_CACHE_TTL` (default `3600`)
- `INGRESS_SESSION_CONTEXT_TTL` (default `1800`)

Optional ICE preload:

- `ICE_SERVICE_URL` (default empty = disabled)
- `ICE_PRELOAD_PATH` (default `/api/v1/hydrate/session`)

Redis write controls:

- `REDIS_KV_READ_ONLY` (default `False`)
- Backward compatible alias: `REDIS_READ_ONLY` (maps to `REDIS_KV_READ_ONLY`)
- When `True`, ingress will avoid **KV/cache writes** (no cache writes, no session/idempotency writes, no attachment metadata writes). Ingress will still be able to **consume and publish** to Redis Streams.

- `REDIS_STREAM_PUBLISH_ENABLED` (default `True`)
- When `False`, ingress will not publish to Redis Streams (no lane publishing and no DLQ publishing).

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
