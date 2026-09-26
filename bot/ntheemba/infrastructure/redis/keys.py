"""Namespaced Redis key construction."""

from __future__ import annotations

import base64


def _segment(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Redis key segments must not be empty")
    return base64.urlsafe_b64encode(cleaned.encode("utf-8")).decode("ascii").rstrip("=")


class RedisKeyspace:
    """Build collision-resistant keys for one Ntheemba environment."""

    def __init__(self, prefix: str, environment: str) -> None:
        self.prefix = prefix.strip().strip(":")
        self.environment = environment.strip().lower()
        if not self.prefix or not self.environment:
            raise ValueError("prefix and environment must not be empty")

    @property
    def root(self) -> str:
        return f"{self.prefix}:{self.environment}"

    def session(self, business_id: str, customer_id: str) -> str:
        return f"{self.root}:session:{_segment(business_id)}:{_segment(customer_id)}"

    def session_archive(self, conversation_id: str, revision: int) -> str:
        if revision < 0:
            raise ValueError("revision must not be negative")
        return f"{self.root}:session-archive:{_segment(conversation_id)}:{revision}"

    def lock(self, business_id: str, customer_id: str) -> str:
        return f"{self.root}:lock:{_segment(business_id)}:{_segment(customer_id)}"

    def platform_session(self, channel_instance_id: str, customer_id: str) -> str:
        return (
            f"{self.root}:platform-session:{_segment(channel_instance_id)}:"
            f"{_segment(customer_id)}"
        )

    def platform_session_archive(self, conversation_id: str, revision: int) -> str:
        if revision < 0:
            raise ValueError("revision must not be negative")
        return f"{self.root}:platform-session-archive:{_segment(conversation_id)}:{revision}"

    def platform_lock(self, channel_instance_id: str, customer_id: str) -> str:
        return (
            f"{self.root}:platform-lock:{_segment(channel_instance_id)}:"
            f"{_segment(customer_id)}"
        )

    def deduplication(self, business_id: str, message_id: str) -> str:
        return f"{self.root}:dedupe:{_segment(business_id)}:{_segment(message_id)}"

    def idempotency(self, key: str) -> str:
        return f"{self.root}:idempotency:{_segment(key)}"

    def customer_cache(self, customer_id: str) -> str:
        return f"{self.root}:customer-cache:{_segment(customer_id)}"

    def runtime_profile(
        self,
        business_id: str,
        channel_instance_id: str,
        runtime_revision: int,
    ) -> str:
        if runtime_revision < 0:
            raise ValueError("runtime_revision must not be negative")
        return (
            f"{self.root}:runtime-profile:{_segment(business_id)}:"
            f"{_segment(channel_instance_id)}:{runtime_revision}"
        )

    def runtime_profile_index(self, business_id: str) -> str:
        return f"{self.root}:runtime-profile-index:{_segment(business_id)}"

    def gateway_inbound_stream(self) -> str:
        return f"{self.root}:gateway:inbound"

    def gateway_outbound_stream(self, gateway_id: str = "") -> str:
        suffix = "" if not gateway_id.strip() else f":{_segment(gateway_id)}"
        return f"{self.root}:gateway:outbound{suffix}"

    def gateway_inbound_dead_letter_stream(self) -> str:
        return f"{self.root}:gateway:inbound:dead-letter"

    def gateway_outbound_dead_letter_stream(self) -> str:
        return f"{self.root}:gateway:outbound:dead-letter"
