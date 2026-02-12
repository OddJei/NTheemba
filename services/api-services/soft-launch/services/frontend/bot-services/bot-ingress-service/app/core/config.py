import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class Settings:
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_decode_responses: bool = os.getenv("REDIS_DECODE_RESPONSES", "True") == "True"
    # Streams / lanes
    incoming_stream: str = os.getenv("INCOMING_STREAM", "ingress:incoming")
    bot_lane_prefix: str = os.getenv("BOT_LANE_PREFIX", "bot:lane:")
    resolved_payload_stream: str = os.getenv("INGRESS_RESOLVED_STREAM", "ingress:resolved_payload")
    consumer_group: str = os.getenv("INGRESS_CONSUMER_GROUP", "ingress-workers")
    poll_count: int = int(os.getenv("INGRESS_POLL_COUNT", "10"))
    poll_block_ms: int = int(os.getenv("INGRESS_POLL_BLOCK_MS", "1000"))
    dlq_stream: str = os.getenv("INGRESS_DLQ_STREAM", "ingress:dlq")
    idempotency_ttl_seconds: int = int(os.getenv("INGRESS_IDEMPOTENCY_TTL", "3600"))
    session_timeout_seconds: int = int(os.getenv("INGRESS_SESSION_TIMEOUT_SECONDS", "1800"))

    # Cache-first enrichment
    cache_enabled: bool = os.getenv("INGRESS_CACHE_ENABLED", "True") == "True"
    bot_cache_ttl_seconds: int = int(os.getenv("INGRESS_BOT_CACHE_TTL", "3600"))
    user_cache_ttl_seconds: int = int(os.getenv("INGRESS_USER_CACHE_TTL", "900"))
    capabilities_cache_ttl_seconds: int = int(os.getenv("INGRESS_CAPABILITIES_CACHE_TTL", "3600"))
    session_context_ttl_seconds: int = int(os.getenv("INGRESS_SESSION_CONTEXT_TTL", "1800"))
    http_timeout_seconds: float = float(os.getenv("HTTP_TIMEOUT_SECONDS", "10.0"))
    bot_service_url: str = os.getenv("BOT_SERVICE_URL", "http://localhost:8000")
    auth_service_url: str = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
    capability_service_url: str = os.getenv("CAPABILITY_SERVICE_URL", "http://localhost:8002")
    # Session service (used by session lookups/creation)
    session_service_url: str = os.getenv("SESSION_SERVICE_URL", "http://localhost:8003")

    # Write controls
    #
    # We split Redis writes into:
    # - KV/cache writes (SET/HSET/EXPIRE, etc.) used for caching + session/idempotency.
    # - Stream publishing (XADD) used to publish envelopes to bot lanes/audit/DLQ.
    #
    # Backward-compat: REDIS_READ_ONLY maps to KV read-only.
    redis_kv_read_only: bool = (
        os.getenv("REDIS_KV_READ_ONLY", os.getenv("REDIS_READ_ONLY", "False")) == "True"
    )
    redis_stream_publish_enabled: bool = os.getenv("REDIS_STREAM_PUBLISH_ENABLED", "True") == "True"

    # Optional ICE integration (used to preload and cache session context)
    ice_service_url: str = os.getenv("ICE_SERVICE_URL", "").strip()
    # Bot-layer contract: ICE hydrate endpoint (sync)
    ice_preload_path: str = os.getenv("ICE_PRELOAD_PATH", "/api/v1/hydrate/session")

    # Hydrate-first mode
    #
    # When enabled, ingress will attempt to hydrate/cache all required blobs (via ICE)
    # before doing enrichment fallbacks to other services.
    ingress_hydrate_first: bool = os.getenv("INGRESS_HYDRATE_FIRST", "False") == "True"
    # If False, enrichment will avoid calling bot/auth/capability HTTP services and will
    # rely on hydrated cache + safe defaults.
    enrich_allow_fallback_http: bool = os.getenv("INGRESS_ENRICH_ALLOW_FALLBACK_HTTP", "True") == "True"

    # Hydration dedupe/backoff knobs
    hydrate_lock_ttl_seconds: int = int(os.getenv("INGRESS_HYDRATE_LOCK_TTL", "20"))
    hydrate_negative_ttl_seconds: int = int(os.getenv("INGRESS_HYDRATE_NEGATIVE_TTL", "30"))
    # Use reference-only payloads (refs + small inline snapshots) instead of embedding full blobs
    ingress_use_refs: bool = os.getenv("INGRESS_USE_REFS", "False") == "True"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
