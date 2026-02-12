"""ice:preload consumer - Async hydration trigger from bot-ingress cache misses.

Consumes requests from 'ice:preload' stream and triggers hydration workflows.
Publishes results to 'ice:hydrated' stream for bot services to consume.
"""

import asyncio
import json
import logging
import os
from typing import Any

import redis.asyncio as redis

from app.config import Config
from app.orchestration.hydrate import HydrationWorkflow
from app.state.repository import IceRepository
from app.cache.redis_client import get_redis_cache

logger = logging.getLogger(__name__)

PRELOAD_STREAM = os.getenv("ICE_PRELOAD_STREAM", "ice:preload")
PRELOAD_GROUP = os.getenv("ICE_PRELOAD_GROUP", "ice-preload-workers")
PRELOAD_CONSUMER = os.getenv("ICE_PRELOAD_CONSUMER_NAME", "preload-1")
HYDRATED_STREAM = os.getenv("ICE_HYDRATED_STREAM", "ice:hydrated")
PRELOAD_DLQ = os.getenv("ICE_PRELOAD_DLQ", "ice:preload:dlq")
PRELOAD_MAX_ATTEMPTS = int(os.getenv("ICE_PRELOAD_MAX_ATTEMPTS", "3"))
PRELOAD_ATTEMPT_TTL = int(os.getenv("ICE_PRELOAD_ATTEMPT_TTL_SECONDS", "3600"))


async def ensure_group(r: redis.Redis, stream: str, group: str) -> None:
    """Create consumer group if it doesn't exist."""
    try:
        await r.xgroup_create(stream, group, id="$", mkstream=True)
        logger.info(f"Created consumer group: {group} on stream: {stream}")
    except redis.ResponseError:
        # Group already exists
        pass


async def mark_attempt_and_should_dlq(r: redis.Redis, stream: str, entry_id: str) -> bool:
    """Track attempt count and return True if should DLQ."""
    key = f"attempts:{stream}:{entry_id}"
    val = await r.incr(key)
    if val == 1:
        await r.expire(key, PRELOAD_ATTEMPT_TTL)
    return val >= PRELOAD_MAX_ATTEMPTS


async def publish_dlq(
    r: redis.Redis,
    original_stream: str,
    entry_id: str,
    payload: dict[str, Any],
    error: str,
) -> None:
    """Publish failed preload request to DLQ."""
    await r.xadd(
        PRELOAD_DLQ,
        {
            "original_stream": original_stream,
            "original_entry_id": entry_id,
            "payload": json.dumps(payload),
            "error": error,
            "timestamp": str(asyncio.get_event_loop().time()),
        },
    )
    logger.warning(
        f"Published to DLQ",
        extra={
            "stream": original_stream,
            "entry_id": entry_id,
            "error": error,
        },
    )


async def handle_preload_request(r: redis.Redis, entry_id: str, data: dict[str, Any]) -> None:
    """Process a single preload hydration request.
    
    Input stream entry should contain:
    {
        "event_id": "evt_20251226_001",
        "session_id": "sess_abc123",
        "user_phone": "260970000001",
        "bot_id": "bot_456",
        "platform": "whatsapp",
        "bot_type": "custom",
        "business_id": "biz_321",
        "required_blobs": ["session", "order_draft", "bot_meta"]
    }
    """
    try:
        # Parse payload
        payload_str = data.get("payload") or data.get("data")
        if isinstance(payload_str, str):
            payload = json.loads(payload_str)
        else:
            payload = payload_str or data

        event_id = payload.get("event_id")
        session_id = payload.get("session_id")
        
        logger.info(
            "preload.processing_request",
            extra={
                "entry_id": entry_id,
                "event_id": event_id,
                "session_id": session_id,
            },
        )

        # Hydrate session
        repo = IceRepository()
        cache = get_redis_cache()
        workflow = HydrationWorkflow(repo, cache)
        
        session_blob = await workflow.hydrate_session(
            session_id=session_id,
            phone_number=payload.get("user_phone", ""),
            business_id=payload.get("business_id", ""),
            correlation_id=event_id,
        )

        # Publish hydrated result
        result = {
            "event_id": event_id,
            "session_id": session_id,
            "status": "success",
            "hydrated_blobs": payload.get("required_blobs", []),
            "session_blob_ref": f"session:{session_id}",
            "timestamp": str(asyncio.get_event_loop().time()),
        }
        
        await r.xadd(
            HYDRATED_STREAM,
            {
                "event_id": event_id or "",
                "session_id": session_id or "",
                "status": "success",
                "payload": json.dumps(result),
            },
        )
        
        logger.info(
            "preload.hydration_success",
            extra={
                "entry_id": entry_id,
                "event_id": event_id,
                "session_id": session_id,
            },
        )

    except Exception as exc:
        logger.exception(
            "preload.processing_failed",
            extra={
                "entry_id": entry_id,
                "error": str(exc),
            },
        )
        raise


async def process_loop(redis_url: str) -> None:
    """Main async loop for preload consumer."""
    r = redis.from_url(redis_url, decode_responses=True)
    await ensure_group(r, PRELOAD_STREAM, PRELOAD_GROUP)

    logger.info(f"Starting preload consumer: {PRELOAD_CONSUMER}")

    while True:
        try:
            # XREADGROUP - wait for new preload requests
            resp = await r.xreadgroup(
                PRELOAD_GROUP,
                PRELOAD_CONSUMER,
                {PRELOAD_STREAM: ">"},
                count=10,
                block=1000,
            )

            if not resp:
                await asyncio.sleep(0.1)
                continue

            # Process each entry
            for stream_name, entries in resp:
                for entry_id, data in entries:
                    try:
                        await handle_preload_request(r, entry_id, data)
                        await r.xack(stream_name, PRELOAD_GROUP, entry_id)
                        
                        # Optionally delete to keep stream lean
                        try:
                            await r.xdel(stream_name, entry_id)
                        except Exception:
                            pass
                            
                    except Exception as exc:
                        should_dlq = await mark_attempt_and_should_dlq(
                            r, PRELOAD_STREAM, entry_id
                        )
                        if should_dlq:
                            await publish_dlq(
                                r,
                                PRELOAD_STREAM,
                                entry_id,
                                data,
                                str(exc),
                            )
                            await r.xack(stream_name, PRELOAD_GROUP, entry_id)
                        
                        logger.exception(
                            "preload.processing_error",
                            extra={
                                "entry_id": entry_id,
                                "should_dlq": should_dlq,
                            },
                        )

        except Exception as exc:
            logger.exception("preload.consumer_loop_error")
            await asyncio.sleep(1)


async def start_preload_consumer(redis_url: str = None) -> None:
    """Start the preload consumer worker.
    
    Usage:
        asyncio.create_task(start_preload_consumer())
    """
    url = redis_url or Config.REDIS_URL
    try:
        await process_loop(url)
    except Exception as exc:
        logger.exception("preload_consumer_failed", extra={"error": str(exc)})
