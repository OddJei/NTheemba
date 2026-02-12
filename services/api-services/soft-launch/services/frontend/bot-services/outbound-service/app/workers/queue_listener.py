from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
from time import perf_counter
from typing import Any, Dict, Optional

import redis

from ..core.config import get_settings
from ..core.http_client import build_http_client
from ..core.redis import get_redis
from ..models import DeliveryReceipt, DlqEntry, OutboundRequest
from ..services.adapter_registry import get_adapter
from ..streams.publisher import publish_dlq, publish_receipt, safe_error
from ..telemetry import metrics

LOG = logging.getLogger("outbound.worker")


def _default_consumer_name() -> str:
    host = socket.gethostname()
    pid = os.getpid()
    return f"{host}-{pid}"


async def _ensure_group(redis_client, stream: str, group: str) -> None:
    try:
        await redis_client.xgroup_create(stream, group, id="0-0", mkstream=True)
    except redis.exceptions.ResponseError as exc:
        # BUSYGROUP means already exists
        if "BUSYGROUP" in str(exc):
            return
        raise


async def _idempotency_check(redis_client, *, event_id: str, ttl_seconds: int) -> bool:
    # returns True if this is the first time seen
    key = f"outbound:idempotency:{event_id}"
    resp = await redis_client.set(key, "1", nx=True, ex=ttl_seconds)
    return bool(resp)


async def start_listener(redis_client=None, settings=None):
    settings = settings or get_settings()
    redis_client = redis_client or get_redis(settings)
    http_client = build_http_client(settings)

    consumer = settings.consumer_name.strip() or _default_consumer_name()

    await _ensure_group(redis_client, settings.outbound_requests_stream, settings.consumer_group)

    try:
        while True:
            try:
                resp = await redis_client.xreadgroup(
                    groupname=settings.consumer_group,
                    consumername=consumer,
                    streams={settings.outbound_requests_stream: ">"},
                    count=settings.poll_count,
                    block=settings.poll_block_ms,
                )

                if not resp:
                    await asyncio.sleep(0)
                    continue

                for _stream, messages in resp:
                    for message_id, message_data in messages:
                        start = perf_counter()
                        raw_payload_str = message_data.get("payload") or message_data.get("message") or "{}"

                        try:
                            raw_payload = json.loads(raw_payload_str)
                            if not isinstance(raw_payload, dict):
                                raise ValueError("payload must be a JSON object")

                            request = OutboundRequest(**raw_payload)

                            if settings.idempotency_enabled:
                                first_seen = await _idempotency_check(
                                    redis_client,
                                    event_id=request.event_id,
                                    ttl_seconds=settings.idempotency_ttl_seconds,
                                )
                                if not first_seen:
                                    metrics.observe_duplicate()
                                    await redis_client.xack(settings.outbound_requests_stream, settings.consumer_group, message_id)
                                    await redis_client.xdel(settings.outbound_requests_stream, message_id)
                                    continue

                            # Resolve platform: prefer `meta.platform`, fall back to legacy `provider` field
                            platform = None
                            try:
                                platform = (request.meta or {}).get("platform") if isinstance(request.meta, dict) else None
                            except Exception:
                                platform = None
                            platform = (platform or request.provider or request.provider_payload.get("platform") if isinstance(request.provider_payload, dict) else None) or "unknown"
                            platform = str(platform).strip().lower()

                            adapter = get_adapter(platform, http_client)
                            result = await adapter.send(request)

                            receipt = DeliveryReceipt(
                                event_id=request.event_id,
                                session_id=request.session_id,
                                provider=platform,
                                provider_message_id=result.provider_message_id,
                                status=result.status,
                                timestamp=DeliveryReceipt.now_iso(),
                                provider_error=result.provider_error,
                                trace_id=request.trace_id,
                            )
                            await publish_receipt(redis_client, settings, receipt)
                            metrics.observe_send(platform, "ok" if result.status != "failed" else "failed")

                            # Retry logic (requeue) for retryable failures
                            if result.status == "failed" and result.retryable:
                                next_attempt = request.attempts + 1
                                if next_attempt < settings.max_attempts:
                                    payload = request.dict()
                                    payload["attempts"] = next_attempt
                                    await redis_client.xadd(settings.outbound_requests_stream, {"payload": json.dumps(payload)})
                                else:
                                    entry = DlqEntry(
                                        event_id=request.event_id,
                                        session_id=request.session_id,
                                        provider=platform,
                                        attempts=next_attempt,
                                        error=safe_error(
                                            result.provider_error.get("code", "SEND_FAILED") if result.provider_error else "SEND_FAILED",
                                            result.provider_error.get("message", "send failed") if result.provider_error else "send failed",
                                            details={"provider_error": result.provider_error or {}},
                                        ),
                                        original_request=request.dict(),
                                        timestamp=DlqEntry.now_iso(),
                                    )
                                    await publish_dlq(redis_client, settings, entry)
                                    metrics.observe_dlq(platform)

                            # Ack original message
                            await redis_client.xack(settings.outbound_requests_stream, settings.consumer_group, message_id)
                            await redis_client.xdel(settings.outbound_requests_stream, message_id)

                            metrics.observe_processed(platform, perf_counter() - start)

                        except Exception as exc:
                            LOG.exception("failed processing outbound message_id=%s: %s", message_id, exc)
                            # On parse/unknown errors: move to DLQ and ack
                            try:
                                provider = "unknown"
                                session_id = raw_payload.get("session_id") if isinstance(raw_payload, dict) else ""
                                event_id = raw_payload.get("event_id") if isinstance(raw_payload, dict) else message_id
                                entry = DlqEntry(
                                    event_id=str(event_id),
                                    session_id=str(session_id),
                                    provider=provider,
                                    attempts=1,
                                    error=safe_error("PROCESSING_ERROR", str(exc)[:500]),
                                    original_request=raw_payload if isinstance(raw_payload, dict) else {"payload": raw_payload_str},
                                    timestamp=DlqEntry.now_iso(),
                                )
                                await publish_dlq(redis_client, settings, entry)
                                metrics.observe_dlq(provider)
                            finally:
                                await redis_client.xack(settings.outbound_requests_stream, settings.consumer_group, message_id)
                                await redis_client.xdel(settings.outbound_requests_stream, message_id)

            except asyncio.CancelledError:
                LOG.info("listener cancelled")
                break
            except Exception:
                LOG.exception("listener loop error, sleeping before retry")
                await asyncio.sleep(1)
    finally:
        await http_client.aclose()
