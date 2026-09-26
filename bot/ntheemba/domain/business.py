"""Business, channel, platform, and resolved capability context models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from ipaddress import ip_address
import re
from types import MappingProxyType
from typing import Any
from urllib.parse import urlparse

from ntheemba.domain.capabilities import Capability


class ChannelScope(StrEnum):
    """Authority scope selected by an exact external channel identity."""

    BUSINESS = "business"
    PLATFORM = "platform"


class ChannelRole(StrEnum):
    """Ntheemba-owned channel roles; marketplace is platform-only."""

    BUSINESS_PRIMARY = "business_primary"
    BUSINESS_SECONDARY = "business_secondary"
    MARKETPLACE = "marketplace"
    PLATFORM_GENERAL = "platform_general"
    PLATFORM_SUPPORT = "platform_support"


class PlatformCapability(StrEnum):
    """Capabilities owned by Ntheemba itself, never by connected businesses."""

    MARKETPLACE = "marketplace"


PLATFORM_CAPABILITY_IDS = frozenset({"marketplace", "platform.marketplace"})

_SECRET_REFERENCE_RE = re.compile(r"^[a-z][a-z0-9_]*:[A-Za-z0-9_.-]+$")
_SENSITIVE_CONFIG_TOKENS = ("token", "secret", "password", "credential", "api_key", "apikey")


def _safe_secret_reference(value: str) -> bool:
    cleaned = value.strip()
    return not cleaned or bool(_SECRET_REFERENCE_RE.fullmatch(cleaned))


def _config_key_may_store_secret(key: str) -> bool:
    normalized = key.strip().casefold().replace("-", "_")
    if normalized.endswith("_reference") or normalized.endswith("_ref"):
        return False
    return any(token in normalized for token in _SENSITIVE_CONFIG_TOKENS)


def _validate_integration_host(hostname: str | None) -> None:
    host = (hostname or "").strip().strip("[]").casefold()
    if not host:
        raise ValueError("base_url must include a hostname")
    if host == "localhost" or host.endswith(".localhost"):
        raise ValueError("base_url must not target localhost")
    try:
        address = ip_address(host)
    except ValueError:
        return
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        raise ValueError("base_url must not target a non-public IP address")


PLATFORM_ROLES = frozenset(
    {ChannelRole.MARKETPLACE, ChannelRole.PLATFORM_GENERAL, ChannelRole.PLATFORM_SUPPORT}
)
BUSINESS_ROLES = frozenset(
    {ChannelRole.BUSINESS_PRIMARY, ChannelRole.BUSINESS_SECONDARY}
)


@dataclass(frozen=True, slots=True)
class BusinessProfile:
    """Configured business whose declarations are validated by Ntheemba."""

    business_id: str
    display_name: str
    adapter_type: str
    declared_capabilities: frozenset[str]
    enabled: bool = True
    business_type: str = ""
    description: str = ""
    runtime_revision: int = 0
    capability_config: MappingProxyType[str, MappingProxyType[str, Any]] = MappingProxyType({})

    def __post_init__(self) -> None:
        for name, value in {
            "business_id": self.business_id,
            "display_name": self.display_name,
            "adapter_type": self.adapter_type,
        }.items():
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if not self.declared_capabilities:
            raise ValueError("declared_capabilities must not be empty")
        platform = sorted(
            item for item in self.declared_capabilities if item in PLATFORM_CAPABILITY_IDS
        )
        if platform:
            raise ValueError(
                "platform capabilities cannot be assigned to a business: " + ", ".join(platform)
            )
        if self.runtime_revision < 0:
            raise ValueError("runtime_revision must not be negative")
        configs = {
            str(capability_id): MappingProxyType(dict(config or {}))
            for capability_id, config in dict(self.capability_config).items()
        }
        object.__setattr__(self, "capability_config", MappingProxyType(configs))


_SAFE_SHOP_LOCATION_KEYS = frozenset({
    "province_id", "province_name", "district_id", "district_name",
    "town_id", "town_name", "area", "landmark", "address",
})


@dataclass(frozen=True, slots=True)
class BusinessShop:
    """Safe, tenant-bound TradeFlow shop routing projection."""

    business_id: str
    shop_id: str
    display_name: str
    status: str = "active"
    is_primary: bool = False
    location: MappingProxyType[str, str] = MappingProxyType({})
    hours_status: str = "unverified"
    source_revision: str = ""

    def __post_init__(self) -> None:
        for name, value in {
            "business_id": self.business_id,
            "shop_id": self.shop_id,
            "display_name": self.display_name,
        }.items():
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if self.status not in {"active", "inactive"}:
            raise ValueError("shop status must be active or inactive")
        if self.hours_status not in {"unverified", "verified"}:
            raise ValueError("hours_status must be unverified or verified")
        location = {str(key): str(value).strip() for key, value in dict(self.location).items() if str(value).strip()}
        unknown = sorted(set(location) - _SAFE_SHOP_LOCATION_KEYS)
        if unknown:
            raise ValueError("shop location contains unsupported fields: " + ", ".join(unknown))
        object.__setattr__(self, "location", MappingProxyType(location))


@dataclass(frozen=True, slots=True)
class ChannelBinding:
    """Exact external channel identity bound to a business or to Ntheemba platform scope.

    ``channel_instance_id`` is retained as the stable internal/legacy identifier.  The
    provider-neutral routing identity is ``(provider, external_session_id,
    recipient_identifier)``.  For current phone transports the legacy ``phone_e164``
    mirrors ``recipient_identifier``.
    """

    channel_instance_id: str
    provider: str
    business_id: str | None
    phone_e164: str
    enabled: bool = True
    scope: ChannelScope = ChannelScope.BUSINESS
    role: ChannelRole = ChannelRole.BUSINESS_PRIMARY
    is_primary: bool = False
    external_session_id: str = ""
    recipient_identifier: str = ""

    def __post_init__(self) -> None:
        channel_instance_id = self.channel_instance_id.strip()
        provider = self.provider.strip().casefold()
        phone_e164 = self.phone_e164.strip().replace(" ", "")
        business_id = None if self.business_id is None else self.business_id.strip()
        for name, value in {
            "channel_instance_id": channel_instance_id,
            "provider": provider,
            "phone_e164": phone_e164,
        }.items():
            if not value:
                raise ValueError(f"{name} must not be empty")
        if not phone_e164.startswith("+") or not phone_e164[1:].isdigit():
            raise ValueError("phone_e164 must use international + notation")

        external_session_id = self.external_session_id.strip() or channel_instance_id
        recipient_identifier = self.recipient_identifier.strip() or phone_e164
        object.__setattr__(self, "channel_instance_id", channel_instance_id)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "phone_e164", phone_e164)
        object.__setattr__(self, "business_id", business_id)
        object.__setattr__(self, "external_session_id", external_session_id)
        object.__setattr__(self, "recipient_identifier", recipient_identifier)

        if self.scope is ChannelScope.BUSINESS:
            if self.business_id is None or not self.business_id.strip():
                raise ValueError("business channels require business_id")
            if self.role not in BUSINESS_ROLES:
                raise ValueError("business channels cannot use platform roles")
        else:
            if self.business_id is not None:
                raise ValueError("platform channels must not have business_id")
            if self.role not in PLATFORM_ROLES:
                raise ValueError("platform channels require a platform role")

    @property
    def exact_identity(self) -> tuple[str, str, str]:
        """Return the provider-neutral exact routing key."""

        return (self.provider, self.external_session_id, self.recipient_identifier)

    @property
    def platform_capabilities(self) -> frozenset[PlatformCapability]:
        """Return capabilities implied by a platform role."""

        if self.scope is ChannelScope.PLATFORM and self.role is ChannelRole.MARKETPLACE:
            return frozenset({PlatformCapability.MARKETPLACE})
        return frozenset()


# Backward-compatible name used throughout the deterministic business runtime.
BusinessChannel = ChannelBinding


@dataclass(frozen=True, slots=True)
class BusinessIntegration:
    """One configured business integration selected by capability at runtime."""

    integration_id: str
    business_id: str
    adapter_type: str
    base_url: str
    provider: str = "google_apps_script"
    api_version: str = "tradeflow.ntheemba.v1"
    auth_reference: str = ""
    status: str = "active"
    enabled: bool = True
    capabilities: frozenset[str] = frozenset()
    config: MappingProxyType[str, Any] = MappingProxyType({})

    def __post_init__(self) -> None:
        for name, value in {
            "integration_id": self.integration_id,
            "business_id": self.business_id,
            "provider": self.provider,
            "adapter_type": self.adapter_type,
            "base_url": self.base_url,
            "api_version": self.api_version,
            "status": self.status,
        }.items():
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if self.status not in {"active", "inactive", "testing", "disabled"}:
            raise ValueError("status must be active, inactive, testing, or disabled")
        parsed_url = urlparse(self.base_url)
        if (
            parsed_url.scheme != "https"
            or not parsed_url.netloc
            or parsed_url.username is not None
            or parsed_url.password is not None
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise ValueError(
                "base_url must be an absolute HTTPS endpoint without credentials, "
                "query, or fragment"
            )
        _validate_integration_host(parsed_url.hostname)
        auth_reference = self.auth_reference.strip()
        if not _safe_secret_reference(auth_reference):
            raise ValueError("auth_reference must be an opaque secret reference, not a raw secret")
        config = dict(self.config)
        forbidden = sorted(str(key) for key in config if _config_key_may_store_secret(str(key)))
        if forbidden:
            raise ValueError(
                "integration config must store secret references instead of secret values: "
                + ", ".join(forbidden)
            )
        for key, value in config.items():
            if str(key).strip().casefold().endswith(("_reference", "_ref")):
                reference = str(value or "").strip()
                if reference and not _safe_secret_reference(reference):
                    raise ValueError(f"integration config reference {key!r} is invalid")
        object.__setattr__(self, "auth_reference", auth_reference)
        object.__setattr__(self, "capabilities", frozenset(self.capabilities))
        object.__setattr__(self, "config", MappingProxyType(config))


@dataclass(frozen=True, slots=True)
class ResolvedBusinessContext:
    """Trusted business context after channel and capability validation."""

    business: BusinessProfile
    channel: ChannelBinding
    capabilities: frozenset[Capability]
    rejected_declarations: frozenset[str] = frozenset()
    integrations: tuple[BusinessIntegration, ...] = ()
    integration: BusinessIntegration | None = None
    runtime_revision: int = 0

    def supports(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def integration_for(self, capability: Capability) -> BusinessIntegration | None:
        if capability not in self.capabilities:
            return None
        if (
            self.integration is not None
            and self.integration.enabled
            and capability.value in self.integration.capabilities
        ):
            return self.integration
        for integration in self.integrations:
            if integration.enabled and capability.value in integration.capabilities:
                return integration
        return None


@dataclass(frozen=True, slots=True)
class ResolvedPlatformContext:
    """Ntheemba-owned context for platform operations such as Marketplace."""

    channel: ChannelBinding
    role: ChannelRole
    capabilities: frozenset[PlatformCapability]

    def __post_init__(self) -> None:
        if self.channel.scope is not ChannelScope.PLATFORM:
            raise ValueError("platform context requires a platform channel")
        if self.role not in PLATFORM_ROLES:
            raise ValueError("platform context requires a platform role")
        if (
            PlatformCapability.MARKETPLACE in self.capabilities
            and self.role is not ChannelRole.MARKETPLACE
        ):
            raise ValueError("marketplace capability requires marketplace channel role")
