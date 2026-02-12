import os
from dataclasses import dataclass
from functools import lru_cache


def _env_bool(name: str, default: str) -> bool:
    return os.getenv(name, default) == "True"


def _env_int_or_none(name: str, default: str | None) -> int | None:
    raw = os.getenv(name)
    if raw is None:
        raw = default
    if raw is None:
        return None
    raw = str(raw).strip()
    if raw == "" or raw.lower() == "none":
        return None
    return int(raw)


@dataclass
class GeminiConfig:
    # Backward/compat envs:
    # - gemini_model, gemini_key (legacy)
    # - INTENT_GEMINI_MODEL, INTENT_GEMINI_API_KEY (canonical)
    model: str = os.getenv("INTENT_GEMINI_MODEL", os.getenv("gemini_model", "gemini-1.5-pro"))
    endpoint: str = os.getenv(
        "INTENT_GEMINI_ENDPOINT",
        "https://generativelanguage.googleapis.com/v1beta/models",
    )
    # Allow comma-separated keys; first will be used by default.
    api_key: str | None = os.getenv("INTENT_GEMINI_API_KEY", os.getenv("gemini_key"))
    timeout_seconds: float = float(os.getenv("INTENT_GEMINI_TIMEOUT_SECONDS", "15.0"))

    # Token limits for Gemini usage: input tokens limit (approximate) and output tokens limit
    max_input_tokens: int = int(os.getenv("INTENT_GEMINI_MAX_INPUT_TOKENS", "450"))
    max_output_tokens: int = int(os.getenv("INTENT_GEMINI_MAX_OUTPUT_TOKENS", "50"))

    # Enable Gemini if a key is present, unless explicitly disabled.
    enabled: bool = _env_bool("INTENT_GEMINI_ENABLED", "True" if api_key else "False")


@dataclass
class StreamConfig:
    requests: str = os.getenv("INTENT_REQUESTS_STREAM", "intent:requests")
    results: str = os.getenv("INTENT_RESULTS_STREAM", "intent:results")
    dlq: str = os.getenv("INTENT_DLQ_STREAM", "intent:dlq")
    maxlen: int | None = _env_int_or_none("INTENT_STREAM_MAXLEN", "10000")


@dataclass
class RedisConfig:
    url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    decode_responses: bool = _env_bool("REDIS_DECODE_RESPONSES", "True")
    consumer_group: str = os.getenv("INTENT_CONSUMER_GROUP", "intent-workers")
    consumer_name: str = os.getenv("INTENT_CONSUMER_NAME", "intent-service")
    read_count: int = int(os.getenv("INTENT_READ_COUNT", "25"))
    read_block_ms: int = int(os.getenv("INTENT_READ_BLOCK_MS", "1000"))


@dataclass
class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "bot-intent-service")
    port: int = int(os.getenv("PORT", "8012"))

    worker_enabled: bool = _env_bool("INTENT_WORKER_ENABLED", "False")

    min_intent_conf: float = float(os.getenv("INTENT_MIN_CONF", "0.70"))
    attachment_soft_limit: int = int(os.getenv("INTENT_ATTACHMENT_SOFT_LIMIT", "6000"))
    attachment_hard_limit: int = int(os.getenv("INTENT_ATTACHMENT_HARD_LIMIT", "8000"))

    idempotency_ttl_seconds: int = int(os.getenv("INTENT_IDEMPOTENCY_TTL", "3600"))
    max_attempts: int = int(os.getenv("INTENT_MAX_ATTEMPTS", "2"))

    gemini: GeminiConfig = GeminiConfig()
    streams: StreamConfig = StreamConfig()
    redis: RedisConfig = RedisConfig()


@lru_cache()
def get_settings() -> Settings:
    return Settings()
