from datetime import datetime, timezone
import json

import logging

LOG = logging.getLogger("bot-ingress.dlq")


async def push_to_dlq(redis, raw_payload: dict, error: str, settings, *, attempts: int = 1):
    payload = {
        "request_id": str(raw_payload.get("request_id") or ""),
        "event_id": str(raw_payload.get("event_id") or ""),
        "error": str(error),
        "attempts": str(attempts),
        "payload": json.dumps(raw_payload),
        "failed_at": datetime.now(timezone.utc).isoformat(),
    }
    if not getattr(settings, "redis_stream_publish_enabled", True):
        LOG.debug("redis_stream_publish_enabled is False — skipping DLQ write for request_id=%s", payload.get("request_id"))
        return

    await redis.xadd(settings.dlq_stream, payload)
