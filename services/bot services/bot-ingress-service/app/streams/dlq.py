from datetime import datetime, timezone
import json


async def push_to_dlq(redis, raw_payload: dict, error: str, settings):
    payload = {
        "request_id": str(raw_payload.get("request_id") or ""),
        "event_id": str(raw_payload.get("event_id") or ""),
        "error": str(error),
        "payload": json.dumps(raw_payload),
        "failed_at": datetime.now(timezone.utc).isoformat(),
    }
    await redis.xadd(settings.dlq_stream, payload)
