from pydantic import BaseModel, Field


class GeminiConfig(BaseModel):
    model: str = Field(default="gemini-1.5-pro")
    endpoint: str = Field(default="https://generativelanguage.googleapis.com/v1beta/models")
    api_key: str | None = Field(default=None, description="API key for Gemini")
    timeout_seconds: float = Field(default=15.0)


class StreamConfig(BaseModel):
    resolved_payload_default: str = Field(default="resolved_payload_default")
    resolved_payload_custom: str = Field(default="resolved_payload_custom")
    default_queue: str = Field(default="default_queue")
    custom_queue: str = Field(default="custom_queue")
    dead_letter_default: str = Field(default="dlq_default_queue")
    dead_letter_custom: str = Field(default="dlq_custom_queue")
    routing_key_prefix: str = Field(default="session:")
    maxlen: int | None = Field(default=10_000, description="Optional max length for output streams")


class RedisConfig(BaseModel):
    url: str = Field(default="redis://localhost:6379/0")
    consumer_group_default: str = Field(default="intent_default_group")
    consumer_group_custom: str = Field(default="intent_custom_group")
    consumer_name: str = Field(default="intent_service")
    read_count: int = Field(default=25)
    read_block_ms: int = Field(default=1000)


class Settings(BaseModel):
    service_name: str = Field(default="bot-intent-service")
    min_intent_conf: float = Field(default=0.70)
    attachment_soft_limit: int = Field(default=6_000)
    attachment_hard_limit: int = Field(default=8_000)
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    streams: StreamConfig = Field(default_factory=StreamConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)


settings = Settings()
