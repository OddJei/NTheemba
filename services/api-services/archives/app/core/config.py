from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _env_bool(name: str, default: str) -> bool:
    return os.getenv(name, default) == "True"


@dataclass
class GeminiConfig:
    model: str = os.getenv("REPLY_GEMINI_MODEL", os.getenv("gemini_model", "gemini-1.5-pro"))
    endpoint: str = os.getenv(
        "REPLY_GEMINI_ENDPOINT",
        os.getenv("INTENT_GEMINI_ENDPOINT", "https://generativelanguage.googleapis.com/v1beta/models"),
    )
    api_key: str | None = os.getenv("REPLY_GEMINI_API_KEY") or os.getenv("INTENT_GEMINI_API_KEY") or os.getenv("gemini_key")
    max_output_tokens: int = int(os.getenv("REPLY_GEMINI_MAX_OUTPUT_TOKENS", "120"))
    enabled: bool = _env_bool("REPLY_GEMINI_ENABLED", "True" if api_key else "False")


@dataclass
class StreamConfig:
    requests: str = os.getenv("REPLY_REQUESTS_STREAM", "reply:requests")
    dlq: str = os.getenv("REPLY_DLQ_STREAM", "reply:dlq")
    outbound_requests: str = os.getenv("OUTBOUND_REQUESTS_STREAM", "outbound:requests")


@dataclass
class RedisConfig:
    url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    decode_responses: bool = _env_bool("REDIS_DECODE_RESPONSES", "True")

    consumer_group: str = os.getenv("REPLY_CONSUMER_GROUP", "reply-workers")
    consumer_name: str = os.getenv("REPLY_CONSUMER_NAME", "reply-service")

    read_count: int = int(os.getenv("REPLY_READ_COUNT", "25"))
    read_block_ms: int = int(os.getenv("REPLY_READ_BLOCK_MS", "1000"))

    idempotency_enabled: bool = _env_bool("REPLY_IDEMPOTENCY_ENABLED", "True")
    idempotency_ttl_seconds: int = int(os.getenv("REPLY_IDEMPOTENCY_TTL_SECONDS", "86400"))


@dataclass
class IdentityConfig:
    persona_name: str = os.getenv("REPLY_PERSONA_NAME", "NTheemba")
    business_name_default: str = os.getenv("REPLY_BUSINESS_NAME_DEFAULT", "your business")
    # persona_at_business|persona_only|none
    prefix_style: str = os.getenv("REPLY_PREFIX_STYLE", "persona_at_business")


@dataclass
class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "reply-service")
    port: int = int(os.getenv("PORT", "8013"))

    worker_enabled: bool = _env_bool("REPLY_WORKER_ENABLED", "True")

    streams: StreamConfig = StreamConfig()
    redis: RedisConfig = RedisConfig()
    identity: IdentityConfig = IdentityConfig()
    gemini: GeminiConfig = GeminiConfig()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
