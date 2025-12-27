from ..core.config import get_settings
from ..models.messages import EnrichedPayload


def _get_session_dict(enriched: EnrichedPayload) -> dict:
    session_val = (enriched.meta or {}).get("session") or {}
    if hasattr(session_val, "dict"):
        return session_val.dict()  # Pydantic model
    return session_val


async def publish_enriched(redis, enriched: EnrichedPayload, settings=None) -> None:
    """Publish the canonical enriched envelope.

    - Primary: `bot:lane:{bot_type}` for low-latency bot processing
    - Audit/replay: `ingress:resolved_payload`
    """

    settings = settings or get_settings()
    session = _get_session_dict(enriched)
    session_id = session.get("session_id")
    bot_type = session.get("bot_type", "default") or "default"

    lane = f"{settings.bot_lane_prefix}{bot_type}"

    # Ensure routing hints exist inside the payload JSON
    routing_hints = {
        "bot_lane": lane,
        "route_version": "v1",
        # If ICE or upstream populated a decision, keep it; otherwise omit.
        "intent_required": bool((enriched.meta or {}).get("session_context", {}).get("intent_required", True)),
    }
    enriched.meta = dict(enriched.meta or {})
    enriched.meta.setdefault("routing_hints", routing_hints)

    payload = enriched.as_stream_dict()
    if session_id:
        payload["routing_key"] = session_id

    # If stream publishing is disabled, skip publishing to Redis streams.
    if not getattr(settings, "redis_stream_publish_enabled", True):
        # Log and return — in some deployments a different publisher may be used.
        import logging

        LOG = logging.getLogger("bot-ingress.publisher")
        LOG.debug("redis_stream_publish_enabled is False — skipping publish_enriched for request=%s", enriched.request_id)
        return

    # Persist canonical envelope for audit/replay.
    await redis.xadd(settings.resolved_payload_stream, payload)
    # Publish to bot lane for immediate processing.
    await redis.xadd(lane, payload)
