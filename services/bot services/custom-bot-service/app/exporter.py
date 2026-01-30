from __future__ import annotations

import os
import time
import asyncio
import logging
from typing import Optional

logger = logging.getLogger("custom_bot.exporter")

# Optional: a small Prometheus scrape endpoint that aggregates simple Redis counters.
# This module is intentionally minimal and designed to be started as a background
# task in deployments that want Prometheus integration without introducing heavy deps.

REDIS_URL = os.getenv("REDIS_URL")
METRIC_PREFIX = os.getenv("CUSTOM_BOT_METRIC_PREFIX", "metrics:custombot:")
SCRAPE_PORT = int(os.getenv("CUSTOM_BOT_PROMETHEUS_PORT", "8081"))
POLL_INTERVAL = float(os.getenv("CUSTOM_BOT_METRIC_POLL_INTERVAL", "5"))


class SimpleExporter:
    def __init__(self, redis_client):
        self.redis = redis_client
        self._stopping = False

    async def collect_metrics(self) -> dict[str, int]:
        # Aggregate counters with the configured prefix. This expects integer values.
        keys = await self.redis.keys(f"{METRIC_PREFIX}*")
        res: dict[str, int] = {}
        if not keys:
            return res
        vals = await self.redis.mget(*keys)
        for k, v in zip(keys, vals):
            try:
                name = k[len(METRIC_PREFIX) :]
                res[name] = int(v) if v is not None else 0
            except Exception:
                logger.exception("metric_parse_failed", extra={"key": k, "value": v})
        return res

    async def run_loop(self):
        while not self._stopping:
            try:
                metrics = await self.collect_metrics()
                # Store a simple snapshot in Redis for scraping or external pickup
                ts = int(time.time())
                await self.redis.set(f"{METRIC_PREFIX}snapshot", str({"ts": ts, "metrics": metrics}))
            except Exception:
                logger.exception("exporter_loop_error")
            await asyncio.sleep(POLL_INTERVAL)

    async def stop(self):
        self._stopping = True


# Helper to start exporter in background
async def start_exporter(redis_client) -> Optional[SimpleExporter]:
    try:
        exp = SimpleExporter(redis_client)
        asyncio.create_task(exp.run_loop())
        logger.info("started simple exporter")
        return exp
    except Exception:
        logger.exception("start_exporter_failed")
        return None
