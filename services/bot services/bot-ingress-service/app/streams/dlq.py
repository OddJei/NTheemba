from datetime import datetime, timezone
import json

import logging

LOG = logging.getLogger("bot-ingress.dlq")


async def push_to_dlq(redis, raw_payload: dict, error: str, settings, *, attempts: int = 1):
    """
    Push a failed request into the Dead Letter Queue (DLQ) stream.

    The DLQ is an append-only stream that stores failed requests for later retrying.
    This function is used to store failed requests into the DLQ stream.

    Args:
        redis: An aioredis client
        raw_payload: A dictionary representing the original request payload
        error: A string representing the error that occurred
        settings: An instance of the Settings class
        attempts: An integer representing the number of times this request has been retried (default: 1)

    Returns:
        None
    """
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
