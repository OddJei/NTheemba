from __future__ import annotations

import asyncio
import json
import logging
import os
from time import perf_counter
from typing import Any, Dict

import redis

from ..core.config import Settings, get_settings
from ..core.redis import get_redis
from ..models import DlqEntry, OutboundRequest, ReplyRequest
from ..services.renderer import ReplyRenderer
from ..streams.publisher import publish_dlq, publish_outbound, safe_error

LOG = logging.getLogger("reply.worker")


async def _ensure_group(redis_client, stream: str, group: str) -> None:
    try:
        await redis_client.xgroup_create(stream, group, id="0-0", mkstream=True)
    except redis.exceptions.ResponseError as exc:
        if "BUSYGROUP" in str(exc):
            return
        raise


async def _idempotency_first_seen(redis_client, *, event_id: str, ttl_seconds: int) -> bool:
    key = f"reply:idempotency:{event_id}"
    resp = await redis_client.set(key, "1", nx=True, ex=ttl_seconds)
    return bool(resp)


def _parse_stream_payload(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """Accept both flat fields and `payload` JSON string."""
    # Prefer explicit `payload` field if present
    payload_str = message_data.get("payload")
    if payload_str and isinstance(payload_str, str):
        try:
            parsed = json.loads(payload_str)
            if isinstance(parsed, dict):
                # Merge top-level stream fields for traceability
                merged = dict(parsed)
                for k in ("event_id", "session_id", "trace_id", "span_id", "next_node"):
                    if message_data.get(k) and k not in merged:
                        merged[k] = message_data.get(k)
                return merged
        except Exception:
            pass

    # Fallback: treat message_data as the object
    return dict(message_data)


def _normalize_reply_request(obj: Dict[str, Any]) -> ReplyRequest:
    # Make sure event_id/session_id exist; fall back to empty strings so DLQ can capture
    event_id = str(obj.get("event_id") or obj.get("id") or "")
    session_id = str(obj.get("session_id") or "")

    # `text` may be top-level or nested
    text = obj.get("text")
    if text is None and isinstance(obj.get("payload"), dict):
        text = obj["payload"].get("text")

    meta = obj.get("meta") if isinstance(obj.get("meta"), dict) else {}

    return ReplyRequest(
        event_id=event_id,
        session_id=session_id,
        channel=obj.get("channel"),
        locale=obj.get("locale") or "en",
        text=text,
        template_id=obj.get("template_id"),
        render_type=obj.get("render_type"),
        template_vars=obj.get("template_vars") if isinstance(obj.get("template_vars"), dict) else {},
        next_node=obj.get("next_node"),
        meta=meta,
        trace_id=obj.get("trace_id"),
        span_id=obj.get("span_id"),
    )


def _platform_from_request(req: ReplyRequest) -> str:
    # Prefer meta.platform, then req.channel
    try:
        p = (req.meta or {}).get("platform")
        if isinstance(p, str) and p.strip():
            return p.strip().lower()
    except Exception:
        pass

    if req.channel:
        return str(req.channel).strip().lower()

    return "http"  # safest default for current outbound implementation


async def start_listener(redis_client=None, settings: Settings | None = None):
    settings = settings or get_settings()
    redis_client = redis_client or get_redis(settings)

    renderer = ReplyRenderer(settings)

    await _ensure_group(redis_client, settings.streams.requests, settings.redis.consumer_group)

    consumer = settings.redis.consumer_name

    while True:
        try:
            resp = await redis_client.xreadgroup(
                groupname=settings.redis.consumer_group,
                consumername=consumer,
                streams={settings.streams.requests: ">"},
                count=settings.redis.read_count,
                block=settings.redis.read_block_ms,
            )

            if not resp:
                await asyncio.sleep(0)
                continue

            for _stream, messages in resp:
                for message_id, message_data in messages:
                    start = perf_counter()
                    try:
                        obj = _parse_stream_payload(message_data)
                        req = _normalize_reply_request(obj)

                        if not req.event_id or not req.session_id:
                            raise ValueError("missing event_id or session_id")

                        if settings.redis.idempotency_enabled:
                            first_seen = await _idempotency_first_seen(
                                redis_client,
                                event_id=req.event_id,
                                ttl_seconds=settings.redis.idempotency_ttl_seconds,
                            )
                            if not first_seen:
                                await redis_client.xack(settings.streams.requests, settings.redis.consumer_group, message_id)
                                await redis_client.xdel(settings.streams.requests, message_id)
                                continue

                        final_text = await renderer.render_text(req)
                        platform = _platform_from_request(req)

                        outbound = OutboundRequest(
                            event_id=req.event_id,
                            session_id=req.session_id,
                            provider=None,
                            meta={"platform": platform, **(req.meta or {})},
                            provider_payload={"type": "text", "text": final_text, "platform": platform},
                            delivery_instructions={"channel": platform},
                            trace_id=req.trace_id,
                        )

                        await publish_outbound(redis_client, settings, outbound)

                        await redis_client.xack(settings.streams.requests, settings.redis.consumer_group, message_id)
                        await redis_client.xdel(settings.streams.requests, message_id)

                        LOG.info(
                            "reply.processed",
                            extra={
                                "event_id": req.event_id,
                                "session_id": req.session_id,
                                "platform": platform,
                                "latency_ms": int((perf_counter() - start) * 1000),
                                "trace_id": req.trace_id,
                            },
                        )

                    except Exception as exc:
                        LOG.exception("reply.failed message_id=%s", message_id)
                        # move to DLQ and ack
                        try:
                            obj = _parse_stream_payload(message_data)
                            req = _normalize_reply_request(obj)
                            entry = DlqEntry(
                                event_id=req.event_id or str(message_id),
                                session_id=req.session_id or "",
                                error=safe_error("REPLY_PROCESSING_ERROR", str(exc)[:500]),
                                original_request=obj,
                                timestamp=DlqEntry.now_iso(),
                            )
                            await publish_dlq(redis_client, settings, entry)
                        finally:
                            await redis_client.xack(settings.streams.requests, settings.redis.consumer_group, message_id)
                            await redis_client.xdel(settings.streams.requests, message_id)

        except asyncio.CancelledError:
            LOG.info("reply listener cancelled")
            break
        except Exception:
            LOG.exception("reply listener loop error")
            await asyncio.sleep(1)
