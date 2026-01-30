from __future__ import annotations

import os
import json
import random
from typing import Any

EVENT_STREAM = os.getenv("CUSTOM_BOT_EVENT_STREAM", "custombot:events")
METRIC_PREFIX = os.getenv("CUSTOM_BOT_METRIC_PREFIX", "metrics:custombot:")
_SAMPLING_RATE = float(os.getenv("CUSTOM_BOT_TELEMETRY_SAMPLING_RATE", "1.0"))


def _should_sample() -> bool:
    try:
        return random.random() < _SAMPLING_RATE
    except Exception:
        return True


async def emit_event(r, name: str, payload: dict[str, Any]) -> str | None:
    """Emit a structured telemetry event to Redis stream. Sampling is applied.

    This function is intended to be scheduled via `asyncio.create_task` to avoid
    blocking request/handler latency.
    """
    if not _should_sample():
        return None
    data = {"event": name, "payload": json.dumps(payload)}
    try:
        return await r.xadd(EVENT_STREAM, data)
    except Exception:
        return None


async def incr_metric(r, name: str, value: int = 1) -> int | None:
    """Increment a simple Redis counter for a metric name. Non-fatal on error."""
    if not _should_sample():
        # still allow metrics sampling to reduce write volume
        return None
    key = METRIC_PREFIX + name
    try:
        return await r.incr(key, value)
    except Exception:
        return None
