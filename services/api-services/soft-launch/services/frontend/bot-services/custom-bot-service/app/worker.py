from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import redis.asyncio as redis

from .processor import handle_entry

logger = logging.getLogger("custom_bot.worker")

STREAM = os.getenv("CUSTOM_BOT_STREAM", "bot:lane:custom")
GROUP = os.getenv("CUSTOM_BOT_CONSUMER_GROUP", "custom-bot-workers")
CONSUMER = os.getenv("CUSTOM_BOT_CONSUMER_NAME", "custom-bot-1")
DLQ_STREAM = os.getenv("CUSTOM_BOT_DLQ_STREAM", "custom-bot:dlq")
ATTEMPT_TTL = int(os.getenv("CUSTOM_BOT_ATTEMPT_TTL_SECONDS", "3600"))
MAX_ATTEMPTS = int(os.getenv("CUSTOM_BOT_MAX_ATTEMPTS", "3"))
CLAIM_IDLE_MS = int(os.getenv("CUSTOM_BOT_CLAIM_IDLE_MS", "2000"))


async def ensure_group(r: redis.Redis, stream: str, group: str) -> None:
    try:
        await r.xgroup_create(stream, group, id="$", mkstream=True)
        logger.info("created consumer group", extra={"stream": stream, "group": group})
    except redis.ResponseError:
        # group exists
        pass


async def mark_attempt_and_should_dlq(r: redis.Redis, stream: str, entry_id: str) -> bool:
    key = f"attempts:{stream}:{entry_id}"
    val = await r.incr(key)
    if val == 1:
        await r.expire(key, ATTEMPT_TTL)
    return val >= MAX_ATTEMPTS


async def publish_dlq(r: redis.Redis, original_stream: str, entry_id: str, payload: dict[str, Any], error: str) -> None:
    await r.xadd(DLQ_STREAM, {"original_stream": original_stream, "original_entry_id": entry_id, "payload": json.dumps(payload), "error": error})


async def process_loop(redis_url: str) -> None:
    r = redis.from_url(redis_url, decode_responses=True)
    await ensure_group(r, STREAM, GROUP)

    claim_start_id = "0-0"

    while True:
        try:
            # XREADGROUP block 1s
            resp = await r.xreadgroup(GROUP, CONSUMER, {STREAM: '>'}, count=10, block=1000)
            if not resp:
                # No new messages: try to claim pending entries (retries).
                try:
                    claimed = await r.xautoclaim(STREAM, GROUP, CONSUMER, CLAIM_IDLE_MS, claim_start_id, count=10)
                    # redis-py returns (next_start_id, messages, deleted_ids)
                    if isinstance(claimed, (list, tuple)) and len(claimed) >= 2:
                        claim_start_id = claimed[0] or "0-0"
                        pending_entries = claimed[1] or []
                    else:
                        pending_entries = []

                    for entry_id, data in pending_entries:
                        try:
                            await handle_entry(r, STREAM, entry_id, data)
                            await r.xack(STREAM, GROUP, entry_id)
                            try:
                                await r.xdel(STREAM, entry_id)
                            except Exception:
                                pass
                        except Exception as exc:
                            should_dlq = await mark_attempt_and_should_dlq(r, STREAM, entry_id)
                            if should_dlq:
                                await publish_dlq(r, STREAM, entry_id, data, str(exc))
                                await r.xack(STREAM, GROUP, entry_id)
                            logger.exception(
                                "processing_pending_entry_failed",
                                exc_info=exc,
                                extra={"stream": STREAM, "entry_id": entry_id},
                            )

                except Exception:
                    # Older Redis or redis-py without XAUTOCLAIM support.
                    pass

                await asyncio.sleep(0.1)
                continue

            # resp is list of (stream, [(id, {k:v}), ...])
            for stream_name, entries in resp:
                for entry_id, data in entries:
                    try:
                        await handle_entry(r, stream_name, entry_id, data)
                        # success -> ack
                        await r.xack(stream_name, GROUP, entry_id)
                        # optionally delete to keep stream small
                        try:
                            await r.xdel(stream_name, entry_id)
                        except Exception:
                            pass
                    except Exception as exc:
                        # increment attempts and possibly DLQ
                        should_dlq = await mark_attempt_and_should_dlq(r, stream_name, entry_id)
                        if should_dlq:
                            await publish_dlq(r, stream_name, entry_id, data, str(exc))
                            await r.xack(stream_name, GROUP, entry_id)
                        logger.exception("processing_entry_failed", exc_info=exc, extra={"stream": stream_name, "entry_id": entry_id})
        except Exception:
            logger.exception("fatal_consumer_loop_error")
            await asyncio.sleep(1)


async def run_worker() -> None:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    await process_loop(redis_url)
