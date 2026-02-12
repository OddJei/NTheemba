import asyncio
import json
import logging
from typing import Any

from ..core.config import get_settings
from ..core.http_client import build_http_client
from ..core.redis import get_redis
from ..ingress.validator import validate_and_check
from ..ingress.enricher import enrich_inbound
from ..ingress.publisher import publish_enriched
from ..services.session_manager import SessionManager
from ..streams.dlq import push_to_dlq
from ..telemetry import metrics
from time import perf_counter

LOG = logging.getLogger("bot-ingress.worker")


async def start_listener(redis=None, settings=None):
    settings = settings or get_settings()
    redis = redis or get_redis(settings)
    http_client = build_http_client(settings)
    session_manager = SessionManager(redis, settings)

    last_id = "0-0"
    try:
        async with http_client:
            # Simple polling loop using XREAD (blocking)
            while True:
                try:
                    resp = await redis.xread({settings.incoming_stream: last_id}, count=settings.poll_count, block=settings.poll_block_ms)
                    if not resp:
                        await asyncio.sleep(0)  # yield control
                        continue

                    for stream, messages in resp:
                        for message_id, message_data in messages:
                            last_id = message_id
                            raw_payload_str = message_data.get("payload") or message_data.get("message") or "{}"
                            try:
                                raw_payload = json.loads(raw_payload_str)
                            except Exception:
                                LOG.exception("invalid json payload: %s", raw_payload_str)
                                continue

                            try:
                                start = perf_counter()
                                inbound = await validate_and_check(raw_payload, session_manager)
                                if inbound is None:
                                    LOG.debug("duplicate request_id, skipping: %s", raw_payload.get("request_id"))
                                    metrics.observe_duplicate()
                                    continue

                                enriched = await enrich_inbound(inbound, http_client, redis, session_manager, settings)

                                # Assign a stable event_id for downstream correlation.
                                # Use request_id as the default stable identifier.
                                enriched.event_id = inbound.request_id
                                try:
                                    if isinstance(enriched.meta, dict) and "session_event" in enriched.meta:
                                        se = enriched.meta.get("session_event")
                                        if isinstance(se, dict):
                                            se["event_id"] = inbound.request_id
                                except Exception:
                                    pass

                                await publish_enriched(redis, enriched, settings)
                                duration = perf_counter() - start
                                metrics.observe_processed(duration)
                                LOG.info("processed and published request_id=%s in %.3fs", inbound.request_id, duration)
                            except Exception as exc:
                                LOG.exception("failed processing incoming message: %s", exc)
                                metrics.observe_dlq()
                                await push_to_dlq(redis, raw_payload, exc, settings, attempts=1)

                except asyncio.CancelledError:
                    LOG.info("listener cancelled")
                    break
                except Exception:
                    LOG.exception("listener loop error, sleeping before retry")
                    await asyncio.sleep(1)
    finally:
        # ensure client is closed if context manager didn't run
        try:
            await http_client.aclose()
        except Exception:
            pass
