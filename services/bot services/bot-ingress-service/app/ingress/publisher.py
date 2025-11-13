import json
from typing import Any

from ..core.config import get_settings
from ..models.messages import EnrichedPayload


async def publish_enriched(redis, enriched: EnrichedPayload, settings=None) -> None:
    settings = settings or get_settings()
    session_id = enriched.meta.session.session_id
    bot_type = enriched.meta.session.bot_type
    lane = settings.resolved_stream_custom if bot_type == "custom" else settings.resolved_stream_default
    payload = enriched.as_stream_dict()
    payload["routing_key"] = session_id
    # XADD; store payload as JSON string
    await redis.xadd(lane, payload)
