from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class Settings:
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_decode_responses: bool = os.getenv("REDIS_DECODE_RESPONSES", "True") == "True"

    outbound_requests_stream: str = os.getenv("OUTBOUND_REQUESTS_STREAM", "outbound:requests")
    outbound_dlq_stream: str = os.getenv("OUTBOUND_DLQ_STREAM", "outbound:dlq")
    platform_stream_prefix: str = os.getenv("OUTBOUND_PLATFORM_STREAM_PREFIX", "outbound:")

    consumer_group: str = os.getenv("OUTBOUND_CONSUMER_GROUP", "outbound-workers")
    consumer_name: str = os.getenv("OUTBOUND_CONSUMER_NAME", "")

    poll_count: int = int(os.getenv("OUTBOUND_POLL_COUNT", "10"))
    poll_block_ms: int = int(os.getenv("OUTBOUND_POLL_BLOCK_MS", "1000"))

    max_attempts: int = int(os.getenv("OUTBOUND_MAX_ATTEMPTS", "3"))

    idempotency_enabled: bool = os.getenv("OUTBOUND_IDEMPOTENCY_ENABLED", "True") == "True"
    idempotency_ttl_seconds: int = int(os.getenv("OUTBOUND_IDEMPOTENCY_TTL_SECONDS", "86400"))

    redis_stream_publish_enabled: bool = os.getenv("REDIS_STREAM_PUBLISH_ENABLED", "True") == "True"

    http_timeout_seconds: float = float(os.getenv("OUTBOUND_HTTP_TIMEOUT_SECONDS", "15"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
