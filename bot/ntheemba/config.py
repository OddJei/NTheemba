"""Application configuration loaded from environment variables."""

from __future__ import annotations

import json
from functools import lru_cache
from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated Ntheemba runtime settings."""

    model_config = SettingsConfigDict(
        env_prefix="NTHEEMBA_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Ntheemba"
    environment: Literal["development", "test", "staging", "production"] = "development"
    version: str = "0.12.0"
    api_prefix: str = "/api/v1"
    docs_enabled: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    tracing_enabled: bool = True
    trace_export_enabled: bool = True
    trace_sample_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    trace_include_running: bool = True
    trace_include_error_messages: bool = False
    trace_error_message_max_length: int = Field(default=250, ge=0, le=10_000)

    gateway_shared_secret: SecretStr | None = None
    # Per-gateway credentials.  This protected JSON object maps a stable
    # Ntheemba gateway principal to its secret; it is intentionally separate
    # from the legacy single gateway shared secret.
    transport_gateway_tokens_json: SecretStr | None = None
    # Development tooling may impersonate only explicitly designated synthetic
    # gateway principals, never every configured transport credential.
    transport_simulator_gateway_ids: str = "openwa-simulator"
    transport_replay_window_seconds: int = Field(default=300, ge=30, le=3_600)
    operator_api_enabled: bool = False
    operator_api_token: SecretStr | None = None
    operator_api_allowed_actors: str = ""
    # JSON object of per-business, one-way onboarding credentials.  This is
    # deliberately separate from the platform operator credential.
    tradeflow_onboarding_tokens_json: SecretStr | None = None
    tradeflow_self_service_onboarding_enabled: bool = False

    ncpc_base_url: str = ""
    ncpc_api_token: SecretStr | None = None
    ncpc_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    gemini_enabled: bool = False
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.0-flash"
    gemini_timeout_seconds: float = Field(default=8.0, gt=0, le=60)
    gemini_retry_count: int = Field(default=1, ge=0, le=3)
    gemini_max_output_tokens: int = Field(default=512, ge=32, le=4096)
    reply_localization_enabled: bool = False
    local_language_blend: float = Field(default=0.15, ge=0.10, le=0.20)
    local_language_variants: str = "bemba,nyanja"
    inbound_worker_consumer_id: str = "ntheemba-inbound-1"
    inbound_worker_poll_seconds: float = Field(default=0.25, gt=0, le=30)

    session_backend: Literal["memory", "redis"] = "memory"
    customer_backend: Literal["memory", "postgres"] = "memory"
    business_backend: Literal["memory", "postgres"] = "memory"
    gateway_queue_backend: Literal["memory", "redis"] = "memory"

    redis_url: SecretStr | None = None
    redis_key_prefix: str = "ntheemba"
    redis_socket_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    session_ttl_seconds: int = Field(default=604_800, ge=300, le=31_536_000)
    session_archive_ttl_seconds: int = Field(default=7_776_000, ge=3_600, le=63_072_000)
    deduplication_ttl_seconds: int = Field(default=604_800, ge=60, le=31_536_000)
    idempotency_ttl_seconds: int = Field(default=2_592_000, ge=60, le=63_072_000)
    lock_ttl_seconds: int = Field(default=30, ge=5, le=300)
    lock_acquire_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    lock_retry_interval_seconds: float = Field(default=0.05, gt=0, le=2)
    gateway_claim_idle_seconds: int = Field(default=60, ge=5, le=3_600)
    gateway_max_delivery_attempts: int = Field(default=5, ge=1, le=100)
    gateway_stream_max_length: int = Field(default=100_000, ge=100, le=10_000_000)

    postgres_dsn: SecretStr | None = None
    postgres_pool_min_size: int = Field(default=1, ge=0, le=50)
    postgres_pool_max_size: int = Field(default=10, ge=1, le=100)
    postgres_pool_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    customer_default_country_code: str = "+260"
    customer_message_retention_days: int = Field(default=180, ge=1, le=3_650)
    customer_summary_retention_days: int = Field(default=730, ge=30, le=7_300)
    customer_question_retention_days: int = Field(default=730, ge=30, le=7_300)
    unsupported_observation_retention_days: int = Field(default=365, ge=30, le=7_300)
    cross_business_recognition_enabled: bool = True

    dev_tools_enabled: bool = True
    dev_tools_token: SecretStr | None = None
    dev_tools_allowed_networks: str = "127.0.0.0/8,::1/128"
    dev_tools_session_ttl_seconds: int = Field(default=3_600, ge=60, le=86_400)

    @field_validator("app_name", "version", "redis_key_prefix", "inbound_worker_consumer_id")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned

    @field_validator("api_prefix")
    @classmethod
    def normalize_api_prefix(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.startswith("/"):
            cleaned = f"/{cleaned}"
        if len(cleaned) > 1:
            cleaned = cleaned.rstrip("/")
        return cleaned

    @field_validator(
        "redis_url",
        "postgres_dsn",
        "dev_tools_token",
        "operator_api_token",
        "tradeflow_onboarding_tokens_json",
        "transport_gateway_tokens_json",
        "ncpc_api_token",
        "gemini_api_key",
        mode="before",
    )
    @classmethod
    def normalize_optional_secret(
        cls,
        value: str | SecretStr | None,
    ) -> SecretStr | None:
        if value is None:
            return None
        raw = value.get_secret_value() if isinstance(value, SecretStr) else value
        cleaned = raw.strip()
        return SecretStr(cleaned) if cleaned else None

    @field_validator("operator_api_allowed_actors", "transport_simulator_gateway_ids")
    @classmethod
    def normalize_operator_api_allowed_actors(cls, value: str) -> str:
        actors = tuple(item.strip() for item in value.split(",") if item.strip())
        if len(actors) != len(set(actors)):
            raise ValueError("operator_api_allowed_actors must not contain duplicates")
        return ",".join(actors)

    @field_validator("gemini_model")
    @classmethod
    def normalize_gemini_model(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("gemini_model must not be empty")
        return cleaned.removeprefix("models/")

    @field_validator("local_language_variants")
    @classmethod
    def normalize_local_language_variants(cls, value: str) -> str:
        variants = tuple(item.strip().lower() for item in value.split(",") if item.strip())
        if not variants:
            raise ValueError("local_language_variants must contain at least one language")
        allowed = {"bemba", "nyanja"}
        unsupported = sorted(set(variants) - allowed)
        if unsupported:
            raise ValueError(f"unsupported local language variant {unsupported[0]!r}")
        if len(variants) != len(set(variants)):
            raise ValueError("local_language_variants must not contain duplicates")
        return ",".join(variants)

    @field_validator("ncpc_base_url")
    @classmethod
    def normalize_ncpc_base_url(cls, value: str, info: ValidationInfo) -> str:
        cleaned = value.strip().rstrip("/")
        if not cleaned:
            return cleaned
        # The canonical development Compose topology keeps NCPC private on the
        # Docker integration network. This narrowly permits that trusted
        # service address; tenant integration endpoints remain HTTPS-only.
        if (
            cleaned == "http://ncpc:8080"
            and info.data.get("environment") in {"development", "test"}
        ):
            return cleaned
        parsed = urlparse(cleaned)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("ncpc_base_url must be an absolute HTTPS endpoint")
        host = (parsed.hostname or "").strip().strip("[]").casefold()
        if host == "localhost" or host.endswith(".localhost"):
            raise ValueError("ncpc_base_url must not target localhost")
        try:
            address = ip_address(host)
        except ValueError:
            address = None
        if address is not None and (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            raise ValueError("ncpc_base_url must not target a non-public IP address")
        return cleaned

    @field_validator("redis_key_prefix")
    @classmethod
    def normalize_key_prefix(cls, value: str) -> str:
        cleaned = value.strip().strip(":")
        if any(character.isspace() for character in cleaned):
            raise ValueError("must not contain whitespace")
        return cleaned

    @field_validator("customer_default_country_code")
    @classmethod
    def normalize_country_code(cls, value: str) -> str:
        cleaned = value.strip().replace(" ", "")
        if not cleaned.startswith("+") or not cleaned[1:].isdigit():
            raise ValueError("must be an international calling code such as +260")
        if not 1 <= len(cleaned[1:]) <= 3:
            raise ValueError("must contain one to three country-code digits")
        return cleaned

    @field_validator("dev_tools_allowed_networks")
    @classmethod
    def normalize_dev_tools_allowed_networks(cls, value: str) -> str:
        networks = [item.strip() for item in value.split(",") if item.strip()]
        if not networks:
            raise ValueError("must contain at least one IP network")
        try:
            parsed = [ip_network(item, strict=False) for item in networks]
        except ValueError as error:
            raise ValueError("contains an invalid IP network") from error
        return ",".join(str(network) for network in parsed)

    @model_validator(mode="after")
    def validate_runtime_backends(self) -> Settings:
        redis_required = any(
            backend == "redis"
            for backend in (self.session_backend, self.gateway_queue_backend)
        )
        postgres_required = any(
            backend == "postgres"
            for backend in (self.customer_backend, self.business_backend)
        )
        if redis_required and self.redis_url is None:
            raise ValueError("redis_url is required for configured Redis backends")
        if postgres_required and self.postgres_dsn is None:
            raise ValueError("postgres_dsn is required for configured PostgreSQL backends")
        if self.postgres_pool_min_size > self.postgres_pool_max_size:
            raise ValueError("postgres_pool_min_size must not exceed postgres_pool_max_size")
        if self.dev_tools_token is not None:
            token = self.dev_tools_token.get_secret_value()
            if len(token) < 32:
                raise ValueError("dev_tools_token must contain at least 32 characters")
        if self.operator_api_enabled:
            if self.operator_api_token is None:
                raise ValueError("operator_api_token is required when operator_api_enabled")
            if len(self.operator_api_token.get_secret_value()) < 32:
                raise ValueError("operator_api_token must contain at least 32 characters")
            if (
                self.environment in {"staging", "production"}
                and not self.operator_api_allowed_actors
            ):
                raise ValueError(
                    "operator_api_allowed_actors is required when operator_api_enabled "
                    "outside development/test"
                )
        if self.tradeflow_self_service_onboarding_enabled or self.tradeflow_onboarding_tokens_json:
            if self.gateway_shared_secret is None:
                raise ValueError(
                    "gateway_shared_secret is required when TradeFlow onboarding is enabled"
                )
            if len(self.gateway_shared_secret.get_secret_value()) < 32:
                raise ValueError(
                    "gateway_shared_secret must contain at least 32 characters when "
                    "TradeFlow onboarding is enabled"
                )
        if self.transport_gateway_tokens_json is not None:
            try:
                values = json.loads(self.transport_gateway_tokens_json.get_secret_value())
            except json.JSONDecodeError as error:
                raise ValueError("transport_gateway_tokens_json must be a JSON object") from error
            if not isinstance(values, dict) or not values:
                raise ValueError("transport_gateway_tokens_json must be a non-empty JSON object")
            for gateway_id, token in values.items():
                if not isinstance(gateway_id, str) or not gateway_id.strip():
                    raise ValueError("transport gateway identifiers must be non-empty strings")
                if not isinstance(token, str) or len(token.strip()) < 32:
                    raise ValueError(
                        "transport gateway credentials must contain at least 32 characters"
                    )
        if self.gemini_enabled and self.gemini_api_key is None:
            raise ValueError("gemini_api_key is required when gemini_enabled")
        if self.reply_localization_enabled:
            if not self.gemini_enabled:
                raise ValueError("gemini_enabled is required when reply localization is enabled")
            if self.gemini_api_key is None:
                raise ValueError(
                    "gemini_api_key is required when reply localization is enabled"
                )
        if self.developer_tools_active:
            configured = set(self.transport_gateway_tokens)
            simulator_ids = set(self.transport_simulator_gateway_ids.split(","))
            if simulator_ids - configured and configured:
                raise ValueError(
                    "transport_simulator_gateway_ids must name configured gateway principals"
                )
        if self.environment in {"development", "test"} and self.dev_tools_enabled:
            has_remote_network = any(
                not network.is_loopback for network in self.parsed_dev_tools_networks
            )
            if has_remote_network and self.dev_tools_token is None:
                raise ValueError(
                    "dev_tools_token is required when non-loopback networks are allowed"
                )
        return self

    @property
    def parsed_dev_tools_networks(self) -> tuple[IPv4Network | IPv6Network, ...]:
        return tuple(
            ip_network(item.strip(), strict=False)
            for item in self.dev_tools_allowed_networks.split(",")
            if item.strip()
        )

    @property
    def developer_tools_active(self) -> bool:
        return self.dev_tools_enabled and self.environment in {"development", "test"}

    @property
    def redis_dsn(self) -> str | None:
        return self.redis_url.get_secret_value() if self.redis_url is not None else None

    @property
    def postgres_connection_dsn(self) -> str | None:
        return self.postgres_dsn.get_secret_value() if self.postgres_dsn is not None else None

    @property
    def transport_gateway_tokens(self) -> dict[str, str]:
        """Return protected gateway credentials without exposing them to callers."""

        if self.transport_gateway_tokens_json is None:
            return {}
        values = json.loads(self.transport_gateway_tokens_json.get_secret_value())
        return {str(key).strip().casefold(): str(value) for key, value in values.items()}

    @property
    def transport_simulator_gateways(self) -> tuple[str, ...]:
        return tuple(item for item in self.transport_simulator_gateway_ids.split(",") if item)

    @property
    def local_language_variant_list(self) -> tuple[str, ...]:
        return tuple(item for item in self.local_language_variants.split(",") if item)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
