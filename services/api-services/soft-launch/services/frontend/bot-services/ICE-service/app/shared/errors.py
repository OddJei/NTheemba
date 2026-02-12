"""Shared error codes and helpers for ICE."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class IceError:
    code: str
    message: str
    http_status: int = 400
    details: Optional[dict] = None


ICE_TEMPORARY_UNAVAILABLE = IceError(
    code="ICE_TEMPORARY_UNAVAILABLE",
    message="Temporary service unavailability",
    http_status=503,
)

ICE_RESERVE_OUT_OF_STOCK = IceError(
    code="ICE_RESERVE_OUT_OF_STOCK",
    message="One or more items are out of stock",
    http_status=409,
)

ICE_RESERVE_PRICE_CHANGED = IceError(
    code="ICE_RESERVE_PRICE_CHANGED",
    message="Price changed during reservation",
    http_status=409,
)
