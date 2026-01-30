# Custom Bot Service — Phase A

This is a minimal Phase A worker for `bot:lane:custom` that demonstrates a production-ready Redis Stream consumer.

Runs a FastAPI health endpoint plus a background worker that:

- reads from Redis stream `bot:lane:custom` using `XREADGROUP`
- acknowledges only on successful processing
- retries up to `CUSTOM_BOT_MAX_ATTEMPTS` (default 3) then pushes to `custom-bot:dlq`
- stores attempt counters in Redis keys `attempts:{stream}:{entry_id}`

Run locally (ensure Redis accessible via `REDIS_URL` env):

```bash
python -m app.main
```

Environment variables:
- `REDIS_URL` (default `redis://localhost:6379/0`)
- `CUSTOM_BOT_STREAM` (default `bot:lane:custom`)
- `CUSTOM_BOT_CONSUMER_GROUP` (default `custom-bot-workers`)
- `CUSTOM_BOT_CONSUMER_NAME` (default `custom-bot-1`)
- `CUSTOM_BOT_DLQ_STREAM` (default `custom-bot:dlq`)
- `CUSTOM_BOT_MAX_ATTEMPTS` (default `3`)

Next steps (Phase B+): idempotency store, OOB reads/writes, handler engine.
