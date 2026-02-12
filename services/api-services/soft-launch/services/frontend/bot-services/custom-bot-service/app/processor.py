from __future__ import annotations

import json
import logging
import os
import asyncio
from typing import Any

from . import idempotency
from .oob_store import OOBStore
from .publish import publish_audit, publish_reply_request
from .runtime_engine import process_event
from .audit_client import emit_audit
from .telemetry import emit_event, incr_metric

logger = logging.getLogger("custom_bot.processor")


async def parse_payload_from_message(data: dict[str, Any]) -> dict[str, Any]:
    # Common stream fields: 'payload' contains JSON string, or message may be the payload itself.
    if not data:
        return {}

    # try common keys
    for k in ("payload", "data", "message", "body"):
        if k in data and data[k]:
            v = data[k]
            if isinstance(v, str):
                try:
                    return json.loads(v)
                except Exception:
                    return {"raw": v}
            if isinstance(v, dict):
                return v

    # fallback: assume data values are the payload
    # flatten simple single-field messages
    if len(data) == 1:
        v = list(data.values())[0]
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {"raw": v}
        if isinstance(v, dict):
            return v

    # as last resort, return the raw dict
    return data


async def handle_entry(redis, stream: str, entry_id: str, data: dict[str, Any]) -> None:
    """Process a single stream entry.

    Responsibilities:
    - parse payload
    - log `event_id`, `session_id`, `bot_type`
    - (placeholder) call downstream handlers (not yet implemented)
    """
    payload = await parse_payload_from_message(data)

    event_id = payload.get("event_id") or payload.get("id") or payload.get("eventId")
    session_id = payload.get("session_id") or payload.get("sessionId")
    bot_type = (payload.get("meta") or {}).get("session", {}).get("bot_type") if payload.get("meta") else payload.get("bot_type")

    # Load OOB (best-effort) to enrich logs and provide handlers with context
    oob_meta = None
    if session_id:
        try:
            store = OOBStore()
            # ensure a default OOB is persisted when missing
            oob, ver = await store.create_default_if_missing(session_id)
            items = (oob.get("cart") or {}).get("items") or []
            items_count = len(items) if isinstance(items, list) else 0
            totals = (oob.get("cart") or {}).get("totals") or {}
            grand_total = totals.get("grand_total")
            oob_meta = {"items_count": items_count, "grand_total": grand_total, "oob_version": ver}
        except Exception:
            logger.exception("oob_load_failed", extra={"session_id": session_id})

    extra = {"stream": stream, "entry_id": entry_id, "event_id": event_id, "session_id": session_id, "bot_type": bot_type}
    if oob_meta:
        extra["oob"] = oob_meta
    logger.info("processing.entry", extra=extra)

    # Idempotency: if event_id is present, avoid double processing.
    if event_id:
        try:
            # if already done, skip
            if await idempotency.is_done(redis, event_id):
                logger.info("entry_skipped_already_done", extra={"event_id": event_id})
                return

            # try to claim lock; if cannot, wait briefly for owner to finish or proceed after retries
            claimed = await idempotency.claim_lock(redis, event_id)
            if not claimed:
                # retry a few times checking for done
                waited = 0
                while waited < 3:
                    if await idempotency.is_done(redis, event_id):
                        logger.info("entry_skipped_done_after_wait", extra={"event_id": event_id})
                        return
                    await asyncio.sleep(0.2)
                    waited += 1
                # last-resort: attempt to claim again (race possible)
                claimed = await idempotency.claim_lock(redis, event_id)

            if not claimed:
                logger.warning("could_not_claim_idempotency_lock_will_proceed", extra={"event_id": event_id})
        except Exception:
            logger.exception("idempotency_check_failed", extra={"event_id": event_id})

    # Phase E (first vertical slice): apply intents -> mutate OOB -> publish reply + audit.
    import time
    started = time.perf_counter()
    result = await process_event(payload=payload, event_id=event_id, session_id=session_id)
    reply_text = str(result.get("reply_text") or "")
    next_node = str(result.get("next_node") or "help")
    intent_ids = list(result.get("intent_ids") or [])
    oob_ref = result.get("oob_ref")
    # propagate trace/span if present from runtime
    trace_id = result.get("trace_id") or result.get("trace") or None
    span_id = result.get("root_span_id") or result.get("span_id") or None

    # Publish reply job and audit record (both must succeed before idempotency is marked done)
    await publish_reply_request(
        redis,
        event_id=event_id,
        session_id=session_id,
        text=reply_text,
        next_node=next_node,
        oob_ref=oob_ref,
        meta={"source": "custom-bot-service", "oob": result.get("oob_summary") or {}},
        template_id=result.get("template_id") if isinstance(result.get("template_id"), str) else None,
        render_type=result.get("render_type") if isinstance(result.get("render_type"), str) else None,
        template_vars=result.get("template_vars") if isinstance(result.get("template_vars"), dict) else None,
        trace_id=trace_id,
        span_id=span_id,
    )
    await publish_audit(
        redis,
        event_id=event_id,
        session_id=session_id,
        intent_ids=[str(x) for x in intent_ids],
        result={"next_node": next_node, "oob_ref": oob_ref, "oob": result.get("oob_summary") or {}},
        trace_id=trace_id,
        span_id=span_id,
    )

    # Also emit to centralized audit service (best-effort, non-blocking)
    try:
        audit_payload = {"event_id": event_id, "session_id": session_id, "intent_ids": [str(x) for x in intent_ids], "next_node": next_node, "oob_ref": oob_ref}
        asyncio.create_task(
            emit_audit(
                service="custom-bot-service",
                event_type="reply_published",
                payload=audit_payload,
                metadata={"trace_id": trace_id, "span_id": span_id},
            )
        )
    except Exception:
        logger.exception("audit_emit_task_failed", extra={"event_id": event_id})

    # Phase G: emit structured telemetry and increment simple metrics
    try:
        latency_ms = int((time.perf_counter() - started) * 1000)
        await emit_event(redis, "message_processed", {"event_id": event_id, "session_id": session_id, "next_node": next_node, "latency_ms": latency_ms})
        await incr_metric(redis, "messages_processed")
        await incr_metric(redis, f"latency_ms_total", latency_ms)
    except Exception:
        # telemetry should not break main flow
        logger.exception("telemetry_emit_failed", extra={"event_id": event_id})

    # On success, mark idempotency done when event_id exists
    if event_id:
        try:
            await idempotency.set_done(redis, event_id)
        except Exception:
            logger.exception("idempotency_set_failed", extra={"event_id": event_id})
