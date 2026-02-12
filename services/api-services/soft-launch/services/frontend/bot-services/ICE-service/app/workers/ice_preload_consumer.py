"""
Phase 5: ICE Preload Consumer Worker

Consumes ice:preload stream (async hydration requests) and processes them
in the background. Triggered by Ingress or Custom Bot when session context
needs to be hydrated asynchronously (non-blocking for user-facing flows).

Purpose:
- Reduce bot service latency by deferring expensive hydration to background worker
- Populate session cache (cache:session_context) for bot services to use
- Track hydration completion in ice:hydrated stream
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import redis.asyncio as redis

from app.services.hydration_workflow import HydrationWorkflow
from app.state.cache import RedisCache
from app.state.repository import AsyncSessionLocal

logger = logging.getLogger("ice.preload_consumer")

# Configuration from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
PRELOAD_STREAM = os.getenv("ICE_PRELOAD_STREAM", "ice:preload")
PRELOAD_GROUP = os.getenv("ICE_PRELOAD_GROUP", "ice-preload-workers")
PRELOAD_CONSUMER = os.getenv("ICE_PRELOAD_CONSUMER", "preload-1")
HYDRATED_STREAM = os.getenv("ICE_HYDRATED_STREAM", "ice:hydrated")
PRELOAD_DLQ_STREAM = os.getenv("ICE_PRELOAD_DLQ_STREAM", "ice:preload:dlq")
PRELOAD_MAX_ATTEMPTS = int(os.getenv("ICE_PRELOAD_MAX_ATTEMPTS", "2"))
PRELOAD_ATTEMPT_TTL_SECONDS = int(os.getenv("ICE_PRELOAD_ATTEMPT_TTL_SECONDS", "3600"))
CLAIM_IDLE_MS = int(os.getenv("ICE_PRELOAD_CLAIM_IDLE_MS", "1000"))


async def ensure_group(r: redis.Redis, stream: str, group: str) -> None:
    """Create consumer group if it doesn't exist."""
    try:
        await r.xgroup_create(stream, group, id="$", mkstream=True)
        logger.info(f"created_consumer_group", extra={"stream": stream, "group": group})
    except redis.ResponseError:
        # Group exists
        pass


async def mark_attempt_and_should_dlq(r: redis.Redis, stream: str, entry_id: str) -> bool:
    """Increment attempt counter and check if should go to DLQ."""
    key = f"attempts:{stream}:{entry_id}"
    val = await r.incr(key)
    if val == 1:
        await r.expire(key, PRELOAD_ATTEMPT_TTL_SECONDS)
    return val >= PRELOAD_MAX_ATTEMPTS


async def publish_hydrated(
    r: redis.Redis,
    event_id: str,
    session_id: str,
    session_blob: dict[str, Any] | None,
    order_draft_blob: dict[str, Any] | None,
    bot_meta_blob: dict[str, Any] | None,
) -> None:
    """Publish hydration result to ice:hydrated stream."""
    payload = {
        "event_id": event_id,
        "session_id": session_id,
        "hydrated_at": None,  # Set by publisher
        "blobs": {
            "session": json.dumps(session_blob) if session_blob else None,
            "order_draft": json.dumps(order_draft_blob) if order_draft_blob else None,
            "bot_meta": json.dumps(bot_meta_blob) if bot_meta_blob else None,
        },
    }
    await r.xadd(
        HYDRATED_STREAM,
        {
            "event_id": event_id,
            "session_id": session_id,
            "payload": json.dumps(payload),
        },
    )


async def publish_dlq(
    r: redis.Redis,
    original_stream: str,
    entry_id: str,
    payload: dict[str, Any],
    error: str,
) -> None:
    """Push failed preload request to DLQ."""
    await r.xadd(
        PRELOAD_DLQ_STREAM,
        {
            "original_stream": original_stream,
            "original_entry_id": entry_id,
            "payload": json.dumps(payload),
            "error": error,
        },
    )


async def handle_preload_entry(
    r: redis.Redis, redis_cache: RedisCache, entry_id: str, data: dict[str, Any]
) -> None:
    """Process a single preload request."""
    # Parse payload
    payload_str = data.get("payload", "{}")
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        payload = {}

    event_id = payload.get("event_id") or entry_id
    session_id = payload.get("session_id")
    user_phone = payload.get("user_phone", "")
    business_id = payload.get("business_id", "")
    required_blobs = payload.get("required_blobs", ["session", "order_draft", "bot_meta"])

    logger.info(
        "preload.processing",
        extra={
            "event_id": event_id,
            "session_id": session_id,
            "required_blobs": required_blobs,
        },
    )

    try:
        # Load database session
        async with AsyncSessionLocal() as db:
            # Run hydration workflow
            workflow = HydrationWorkflow(db, redis_cache)
            
            # Hydrate session with empty phone/business (async preload doesn't need auth)
            session_blob = None
            order_draft_blob = None
            bot_meta_blob = None

            if "session" in required_blobs:
                session_blob = await workflow.hydrate_session(
                    session_id=session_id,
                    phone_number=user_phone or "",
                    business_id=business_id or "",
                    correlation_id=event_id,
                )

            if "order_draft" in required_blobs:
                order_draft_blob = await workflow.hydrate_order_draft(
                    session_id=session_id,
                    correlation_id=event_id,
                )

            if "bot_meta" in required_blobs:
                bot_meta_blob = await workflow.hydrate_bot_meta(
                    session_id=session_id,
                    correlation_id=event_id,
                )

        # Cache blobs in Redis (short TTL, will be re-fetched if not used)
        idem_key = payload.get("idempotency_key") or event_id
        if session_blob:
            await redis_cache.set_hydrated_session(idem_key, {"session": session_blob}, ttl_minutes=10)
        if order_draft_blob:
            await redis_cache.set_order_draft(session_id, order_draft_blob, ttl_minutes=10)

        # Publish result to ice:hydrated stream
        await publish_hydrated(
            r,
            event_id=event_id,
            session_id=session_id,
            session_blob=session_blob,
            order_draft_blob=order_draft_blob,
            bot_meta_blob=bot_meta_blob,
        )

        logger.info(
            "preload.success",
            extra={
                "event_id": event_id,
                "session_id": session_id,
                "cached": True,
            },
        )

    except Exception as exc:
        logger.exception(
            "preload.failed",
            exc_info=exc,
            extra={
                "event_id": event_id,
                "session_id": session_id,
                "entry_id": entry_id,
            },
        )
        raise


async def process_loop(redis_url: str = REDIS_URL) -> None:
    """Main async loop: consume ice:preload stream and process requests."""
    r = redis.from_url(redis_url, decode_responses=True)
    redis_cache = RedisCache(redis_url=redis_url)
    
    await ensure_group(r, PRELOAD_STREAM, PRELOAD_GROUP)

    claim_start_id = "0-0"

    while True:
        try:
            # XREADGROUP block 1s
            resp = await r.xreadgroup(
                PRELOAD_GROUP, PRELOAD_CONSUMER, {PRELOAD_STREAM: ">"}, count=10, block=1000
            )
            if not resp:
                # No new messages: try to claim pending entries (retries)
                try:
                    claimed = await r.xautoclaim(
                        PRELOAD_STREAM, PRELOAD_GROUP, PRELOAD_CONSUMER, CLAIM_IDLE_MS, claim_start_id, count=10
                    )
                    if isinstance(claimed, (list, tuple)) and len(claimed) >= 2:
                        claim_start_id = claimed[0] or "0-0"
                        pending_entries = claimed[1] or []
                    else:
                        pending_entries = []

                    for entry_id, data in pending_entries:
                        try:
                            await handle_preload_entry(r, redis_cache, entry_id, data)
                            await r.xack(PRELOAD_STREAM, PRELOAD_GROUP, entry_id)
                            try:
                                await r.xdel(PRELOAD_STREAM, entry_id)
                            except Exception:
                                pass
                        except Exception as exc:
                            should_dlq = await mark_attempt_and_should_dlq(r, PRELOAD_STREAM, entry_id)
                            if should_dlq:
                                await publish_dlq(r, PRELOAD_STREAM, entry_id, data, str(exc))
                                await r.xack(PRELOAD_STREAM, PRELOAD_GROUP, entry_id)
                            logger.exception(
                                "processing_pending_entry_failed",
                                exc_info=exc,
                                extra={"stream": PRELOAD_STREAM, "entry_id": entry_id},
                            )

                except Exception:
                    # Older Redis or redis-py without XAUTOCLAIM support
                    pass

                await asyncio.sleep(0.1)
                continue

            # Process new messages
            for stream_name, entries in resp:
                for entry_id, data in entries:
                    try:
                        await handle_preload_entry(r, redis_cache, entry_id, data)
                        await r.xack(stream_name, PRELOAD_GROUP, entry_id)
                        try:
                            await r.xdel(stream_name, entry_id)
                        except Exception:
                            pass
                    except Exception as exc:
                        should_dlq = await mark_attempt_and_should_dlq(r, stream_name, entry_id)
                        if should_dlq:
                            await publish_dlq(r, stream_name, entry_id, data, str(exc))
                            await r.xack(stream_name, PRELOAD_GROUP, entry_id)
                        logger.exception(
                            "processing_entry_failed",
                            exc_info=exc,
                            extra={"stream": stream_name, "entry_id": entry_id},
                        )

        except Exception as exc:
            logger.exception("process_loop_error", exc_info=exc)
            await asyncio.sleep(1)


async def start_preload_worker() -> None:
    """Start the preload consumer worker (for use in FastAPI lifespan)."""
    logger.info("starting_preload_worker")
    try:
        await process_loop()
    except asyncio.CancelledError:
        logger.info("preload_worker_cancelled")
    except Exception as exc:
        logger.exception("preload_worker_error", exc_info=exc)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(process_loop())
