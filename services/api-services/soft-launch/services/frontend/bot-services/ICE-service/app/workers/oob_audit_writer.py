"""
Phase 5: OOB Audit Writer Worker

Consumes oob:audit stream (Order Object mutation events) and persists them
to PostgreSQL for audit trail, replay, and analytics.

Purpose:
- Append-only audit log of all OOB mutations (immutable record)
- Enable order reconstruction from audit trail
- Support audit queries (who changed what, when)
- Enable replay for debugging/recovery
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any
from datetime import datetime

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.state.repository import AsyncSessionLocal

logger = logging.getLogger("ice.audit_writer")

# Configuration from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
AUDIT_STREAM = os.getenv("ICE_AUDIT_STREAM", "oob:audit")
AUDIT_GROUP = os.getenv("ICE_AUDIT_GROUP", "ice-audit-writers")
AUDIT_CONSUMER = os.getenv("ICE_AUDIT_CONSUMER", "audit-writer-1")
AUDIT_DLQ_STREAM = os.getenv("ICE_AUDIT_DLQ_STREAM", "oob:audit:dlq")
AUDIT_MAX_ATTEMPTS = int(os.getenv("ICE_AUDIT_MAX_ATTEMPTS", "3"))
AUDIT_ATTEMPT_TTL_SECONDS = int(os.getenv("ICE_AUDIT_ATTEMPT_TTL_SECONDS", "3600"))
CLAIM_IDLE_MS = int(os.getenv("ICE_AUDIT_CLAIM_IDLE_MS", "2000"))


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
        await r.expire(key, AUDIT_ATTEMPT_TTL_SECONDS)
    return val >= AUDIT_MAX_ATTEMPTS


async def persist_audit_entry(
    db: AsyncSession,
    event_id: str,
    session_id: str,
    order_id: str | None,
    event_type: str,
    intent_ids: list[str],
    oob_patch: list[dict[str, Any]],
    result: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> None:
    """Persist audit entry to oob_audit table."""
    now = datetime.utcnow().isoformat()

    # Insert into oob_audit table
    query = text("""
        INSERT INTO oob_audit (
            event_id, session_id, order_id, event_type,
            intent_ids, oob_patch, result, metadata,
            created_at
        ) VALUES (
            :event_id, :session_id, :order_id, :event_type,
            :intent_ids, :oob_patch, :result, :metadata,
            :created_at
        )
    """)

    await db.execute(
        query,
        {
            "event_id": event_id,
            "session_id": session_id,
            "order_id": order_id,
            "event_type": event_type,
            "intent_ids": json.dumps(intent_ids),
            "oob_patch": json.dumps(oob_patch),
            "result": json.dumps(result),
            "metadata": json.dumps(metadata or {}),
            "created_at": now,
        },
    )

    await db.commit()


async def handle_audit_entry(db: AsyncSession, entry_id: str, data: dict[str, Any]) -> None:
    """Process a single audit event and persist to database."""
    # Parse payload
    payload_str = data.get("payload", "{}")
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        payload = {}

    event_id = payload.get("event_id") or entry_id
    session_id = payload.get("session_id")
    order_id = payload.get("order_id")
    intent_ids = payload.get("intent_ids", [])
    result = payload.get("result", {})
    oob_patch = result.get("oob_patch", [])

    logger.info(
        "audit.processing",
        extra={
            "event_id": event_id,
            "session_id": session_id,
            "order_id": order_id,
            "patch_operations": len(oob_patch),
        },
    )

    try:
        # Determine event type from patch operations
        event_type = "oob_mutation"
        if oob_patch:
            first_op_path = oob_patch[0].get("path", "")
            if "/cart" in first_op_path:
                event_type = "cart_mutation"
            elif "/payment" in first_op_path:
                event_type = "payment_mutation"
            elif "/delivery" in first_op_path:
                event_type = "delivery_mutation"

        # Persist to database
        await persist_audit_entry(
            db,
            event_id=event_id,
            session_id=session_id,
            order_id=order_id,
            event_type=event_type,
            intent_ids=intent_ids,
            oob_patch=oob_patch,
            result=result,
            metadata={"entry_id": entry_id},
        )

        logger.info(
            "audit.persisted",
            extra={
                "event_id": event_id,
                "session_id": session_id,
                "event_type": event_type,
            },
        )

    except Exception as exc:
        logger.exception(
            "audit.persist_failed",
            exc_info=exc,
            extra={
                "event_id": event_id,
                "session_id": session_id,
                "entry_id": entry_id,
            },
        )
        raise


async def publish_dlq(
    r: redis.Redis,
    original_stream: str,
    entry_id: str,
    payload: dict[str, Any],
    error: str,
) -> None:
    """Push failed audit entry to DLQ."""
    await r.xadd(
        AUDIT_DLQ_STREAM,
        {
            "original_stream": original_stream,
            "original_entry_id": entry_id,
            "payload": json.dumps(payload),
            "error": error,
        },
    )


async def process_loop(redis_url: str = REDIS_URL) -> None:
    """Main async loop: consume oob:audit stream and persist to database."""
    r = redis.from_url(redis_url, decode_responses=True)

    await ensure_group(r, AUDIT_STREAM, AUDIT_GROUP)

    claim_start_id = "0-0"

    while True:
        try:
            # XREADGROUP block 1s
            resp = await r.xreadgroup(
                AUDIT_GROUP, AUDIT_CONSUMER, {AUDIT_STREAM: ">"}, count=10, block=1000
            )
            if not resp:
                # No new messages: try to claim pending entries (retries)
                try:
                    claimed = await r.xautoclaim(
                        AUDIT_STREAM, AUDIT_GROUP, AUDIT_CONSUMER, CLAIM_IDLE_MS, claim_start_id, count=10
                    )
                    if isinstance(claimed, (list, tuple)) and len(claimed) >= 2:
                        claim_start_id = claimed[0] or "0-0"
                        pending_entries = claimed[1] or []
                    else:
                        pending_entries = []

                    for entry_id, data in pending_entries:
                        try:
                            async with AsyncSessionLocal() as db:
                                await handle_audit_entry(db, entry_id, data)
                            await r.xack(AUDIT_STREAM, AUDIT_GROUP, entry_id)
                            try:
                                await r.xdel(AUDIT_STREAM, entry_id)
                            except Exception:
                                pass
                        except Exception as exc:
                            should_dlq = await mark_attempt_and_should_dlq(r, AUDIT_STREAM, entry_id)
                            if should_dlq:
                                await publish_dlq(r, AUDIT_STREAM, entry_id, data, str(exc))
                                await r.xack(AUDIT_STREAM, AUDIT_GROUP, entry_id)
                            logger.exception(
                                "processing_pending_entry_failed",
                                exc_info=exc,
                                extra={"stream": AUDIT_STREAM, "entry_id": entry_id},
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
                        async with AsyncSessionLocal() as db:
                            await handle_audit_entry(db, entry_id, data)
                        await r.xack(stream_name, AUDIT_GROUP, entry_id)
                        try:
                            await r.xdel(stream_name, entry_id)
                        except Exception:
                            pass
                    except Exception as exc:
                        should_dlq = await mark_attempt_and_should_dlq(r, stream_name, entry_id)
                        if should_dlq:
                            await publish_dlq(r, stream_name, entry_id, data, str(exc))
                            await r.xack(stream_name, AUDIT_GROUP, entry_id)
                        logger.exception(
                            "processing_entry_failed",
                            exc_info=exc,
                            extra={"stream": stream_name, "entry_id": entry_id},
                        )

        except Exception as exc:
            logger.exception("process_loop_error", exc_info=exc)
            await asyncio.sleep(1)


async def start_audit_writer() -> None:
    """Start the audit writer worker (for use in FastAPI lifespan)."""
    logger.info("starting_audit_writer")
    try:
        await process_loop()
    except asyncio.CancelledError:
        logger.info("audit_writer_cancelled")
    except Exception as exc:
        logger.exception("audit_writer_error", exc_info=exc)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(process_loop())
