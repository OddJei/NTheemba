import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class Settings:
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_decode_responses: bool = os.getenv("REDIS_DECODE_RESPONSES", "True") == "True"
    incoming_stream: str = os.getenv("INCOMING_STREAM", "incoming_messages")
    consumer_group: str = os.getenv("INGRESS_CONSUMER_GROUP", "ingress-workers")
    poll_count: int = int(os.getenv("INGRESS_POLL_COUNT", "10"))
    poll_block_ms: int = int(os.getenv("INGRESS_POLL_BLOCK_MS", "1000"))
    resolved_stream_default: str = os.getenv("RESOLVED_STREAM_DEFAULT", "resolved_payload_default")
    resolved_stream_custom: str = os.getenv("RESOLVED_STREAM_CUSTOM", "resolved_payload_custom")
    dlq_stream: str = os.getenv("INGRESS_DLQ_STREAM", "ingress_dlq")
    idempotency_ttl_seconds: int = int(os.getenv("INGRESS_IDEMPOTENCY_TTL", "3600"))
    session_timeout_seconds: int = int(os.getenv("INGRESS_SESSION_TIMEOUT_SECONDS", "1800"))
    http_timeout_seconds: float = float(os.getenv("HTTP_TIMEOUT_SECONDS", "10.0"))
    bot_service_url: str = os.getenv("BOT_SERVICE_URL", "http://localhost:8000")
    auth_service_url: str = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
    capability_service_url: str = os.getenv("CAPABILITY_SERVICE_URL", "http://localhost:8002")
    # Session service (used by session lookups/creation)
    session_service_url: str = os.getenv("SESSION_SERVICE_URL", "http://localhost:8003")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
