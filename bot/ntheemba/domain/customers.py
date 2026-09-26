"""Minimal platform customer and business-client boundary models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal


def _utc_now() -> datetime:
    return datetime.now(UTC)


def normalize_phone_e164(value: str, *, default_country_code: str = "260") -> str:
    """Normalise a Zambian/local or international phone into a stable E.164-like value."""

    digits = "".join(character for character in value if character.isdigit())
    if not digits:
        raise ValueError("phone number must contain digits")
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = f"{default_country_code}{digits[1:]}"
    elif not digits.startswith(default_country_code) and len(digits) <= 10:
        digits = f"{default_country_code}{digits}"
    if len(digits) < 9 or len(digits) > 15:
        raise ValueError("phone number length is invalid")
    return f"+{digits}"


@dataclass(frozen=True, slots=True)
class PlatformCustomer:
    """Minimal identity Ntheemba may reuse with consent across businesses."""

    customer_id: str
    phone_e164: str
    preferred_name: str = ""
    preferred_language: str = "en"
    created_at: datetime = field(default_factory=_utc_now)
    last_seen_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not self.customer_id.strip():
            raise ValueError("customer_id must not be empty")
        if normalize_phone_e164(self.phone_e164) != self.phone_e164:
            raise ValueError("phone_e164 must already be normalised")
        if self.created_at.tzinfo is None or self.last_seen_at.tzinfo is None:
            raise ValueError("customer timestamps must be timezone-aware")


@dataclass(frozen=True, slots=True)
class BusinessClientLink:
    """Private relationship between a platform customer and one business client."""

    business_id: str
    customer_id: str
    external_client_id: str
    business_display_name: str = ""
    first_seen_at: datetime = field(default_factory=_utc_now)
    last_seen_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        for name, value in {
            "business_id": self.business_id,
            "customer_id": self.customer_id,
            "external_client_id": self.external_client_id,
        }.items():
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if self.first_seen_at.tzinfo is None or self.last_seen_at.tzinfo is None:
            raise ValueError("client-link timestamps must be timezone-aware")


@dataclass(frozen=True, slots=True)
class MinimalBusinessClient:
    """Customer-safe subset returned by a TradeFlow client capability."""

    client_id: str
    display_name: str
    phone_e164: str
    status: str = "active"

    def __post_init__(self) -> None:
        if not self.client_id.strip() or not self.display_name.strip():
            raise ValueError("client_id and display_name must not be empty")
        if normalize_phone_e164(self.phone_e164) != self.phone_e164:
            raise ValueError("phone_e164 must already be normalised")
        if not self.status.strip():
            raise ValueError("status must not be empty")


@dataclass(frozen=True, slots=True)
class LoyaltyStatus:
    """Business-calculated loyalty result that Ntheemba may explain."""

    client_id: str
    tier: str
    points: Decimal
    next_tier: str = ""
    points_needed: Decimal | None = None
    reward_description: str = ""
    discount_percent: Decimal = Decimal("0")
    discount_scope: str = ""

    def __post_init__(self) -> None:
        if not self.client_id.strip() or not self.tier.strip():
            raise ValueError("client_id and tier must not be empty")
        if self.points < 0 or self.discount_percent < 0:
            raise ValueError("loyalty values must not be negative")
        if self.points_needed is not None and self.points_needed < 0:
            raise ValueError("points_needed must not be negative")
