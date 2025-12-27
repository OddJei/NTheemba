from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from redis.exceptions import ResponseError
from pydantic import ValidationError

from .core.config import get_settings
from .core.redis import RedisClient
from .models.schemas import IntentRequest
from .services.intent_service import service
from .services.publisher import IntentPublisher

LOG = logging.getLogger("bot-intent.worker")


def _maybe_parse_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    if not (text.startswith("{") or text.startswith("[")):
        return value
    try:
        return json.loads(text)
    except Exception:
        return value


def _parse_request(fields: dict[str, Any]) -> tuple[IntentRequest, dict[str, Any]]:
    """Parse a request from stream fields.

    Supports either:
    - a single `payload` field containing JSON, or
    - direct top-level fields.
    """

    if "payload" in fields:
        raw_payload = fields.get("payload")
        data = _maybe_parse_json(raw_payload)
        if not isinstance(data, dict):
            data = {"raw_text": str(raw_payload)}
    else:
        data = dict(fields)

    # Normalize nested JSON strings.
    if "enriched_meta" in data:
        data["enriched_meta"] = _maybe_parse_json(data.get("enriched_meta"))

    request = IntentRequest.model_validate(data)
    return request, data


def _backoff_seconds(attempts: int) -> float:
    # Exponential backoff with a small cap.
    # attempts=1 means first failure -> ~0.5s, attempts=2 -> ~1s, attempts=3 -> ~2s, etc.
    return min(0.5 * (2 ** max(attempts - 1, 0)), 10.0)


async def _ensure_consumer_group(redis) -> None:
    settings = get_settings()
    try:
        await redis.xgroup_create(
            name=settings.streams.requests,
            groupname=settings.redis.consumer_group,
            id="$",
            mkstream=True,
        )
    except ResponseError as exc:
        # BUSYGROUP Consumer Group name already exists
        if "BUSYGROUP" not in str(exc):
            raise


async def worker_loop() -> None:
    settings = get_settings()
    redis = await RedisClient.get_client()
    publisher = IntentPublisher(redis)

    await _ensure_consumer_group(redis)

    LOG.info(
        "Intent worker started group=%s consumer=%s stream=%s",
        settings.redis.consumer_group,
        settings.redis.consumer_name,
        settings.streams.requests,
    )

    while True:
        try:
            resp = await redis.xreadgroup(
                groupname=settings.redis.consumer_group,
                consumername=settings.redis.consumer_name,
                streams={settings.streams.requests: ">"},
                count=settings.redis.read_count,
                block=settings.redis.read_block_ms,
            )

            if not resp:
                continue

            for stream_name, messages in resp:
                for message_id, fields in messages:
                    attempts = int(fields.get("attempts", "0") or "0")

                    try:
                        request, raw_dict = _parse_request(fields)

                        done_key = f"idempotency:request:{request.event_id}"
                        if await redis.get(done_key):
                            await redis.xack(settings.streams.requests, settings.redis.consumer_group, message_id)
                            continue

                        result = await service.resolve(request)
                        await publisher.publish_result(result)

                        # Mark done only after publishing result (so retries remain possible on failures).
                        await redis.set(done_key, "1", ex=settings.idempotency_ttl_seconds)

                        await redis.xack(settings.streams.requests, settings.redis.consumer_group, message_id)

                    except ValidationError as exc:
                        # Permanent: schema validation errors should DLQ immediately.
                        raw_fallback = dict(fields)
                        raw_fallback.setdefault("_stream_message_id", message_id)
                        await publisher.publish_dlq(request=raw_fallback, error=f"validation_error: {exc}", attempts=attempts + 1)
                        await redis.xack(settings.streams.requests, settings.redis.consumer_group, message_id)

                    except Exception as exc:
                        raw_fallback = raw_dict if "raw_dict" in locals() else dict(fields)
                        raw_fallback.setdefault("_stream_message_id", message_id)

                        next_attempts = attempts + 1
                        if next_attempts >= settings.max_attempts:
                            await publisher.publish_dlq(request=raw_fallback, error=str(exc), attempts=next_attempts)
                            await redis.xack(settings.streams.requests, settings.redis.consumer_group, message_id)
                            continue

                        # Requeue with attempts incremented (best-effort).
                        delay = _backoff_seconds(next_attempts)
                        await asyncio.sleep(delay)

                        # Preserve the original payload format; either re-add `payload` JSON or direct fields.
                        requeue_fields = dict(fields)
                        requeue_fields["attempts"] = str(next_attempts)
                        await redis.xadd(settings.streams.requests, requeue_fields)

                        # Ack the failed message so it doesn't stay pending forever.
                        await redis.xack(settings.streams.requests, settings.redis.consumer_group, message_id)

        except asyncio.CancelledError:
            LOG.info("Intent worker cancelled")
            raise
        except Exception as exc:
            LOG.exception("Intent worker loop error: %s", exc)
            await asyncio.sleep(1.0)
