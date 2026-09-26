"""Typed product-order draft and completeness rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import uuid4

from ntheemba.domain.enums import FulfilmentMethod
from ntheemba.domain.product_resolution import ResolvedProduct


@dataclass(frozen=True, slots=True)
class PriceSnapshot:
    """Price explicitly accepted for the current order review."""

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("price amount must not be negative")
        currency = self.currency.strip().upper()
        if len(currency) != 3:
            raise ValueError("currency must use a three-letter code")
        object.__setattr__(self, "currency", currency)


@dataclass(slots=True)
class OrderDraft:
    """Mutable order data owned by one conversation session."""

    product: ResolvedProduct | None = None
    quantity: int | None = None
    fulfilment_method: FulfilmentMethod | None = None
    delivery_details: str | None = None
    customer_name: str | None = None
    contact_number: str | None = None
    price_snapshot: PriceSnapshot | None = None
    availability_confirmed: bool = False
    validation_reference: str | None = None
    idempotency_key: str = field(default_factory=lambda: f"ORDER-{uuid4()}")
    submitted_request_id: str | None = None
    submitted_status: str | None = None

    def __post_init__(self) -> None:
        if not self.idempotency_key.strip():
            raise ValueError("idempotency_key must not be empty")
        if (self.submitted_request_id is None) != (self.submitted_status is None):
            raise ValueError("submitted_request_id and submitted_status must be supplied together")

    def select_product(self, product: ResolvedProduct) -> None:
        """Select a product and invalidate price/stock validation."""

        self.product = product
        self._clear_validation_and_submission()

    def set_quantity(self, quantity: int) -> None:
        """Set a positive whole-number quantity."""

        if quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        self.quantity = quantity
        self._clear_validation_and_submission()

    def set_fulfilment_method(self, method: FulfilmentMethod) -> None:
        """Set collection or delivery."""

        self.fulfilment_method = method
        if method == FulfilmentMethod.COLLECTION:
            self.delivery_details = None
        self._clear_validation_and_submission()

    def set_delivery_details(self, details: str) -> None:
        """Store usable delivery directions."""

        cleaned = details.strip()
        if len(cleaned) < 5:
            raise ValueError("delivery details must contain at least five characters")
        self.delivery_details = cleaned
        self._clear_validation_and_submission()

    def set_customer(self, name: str, contact_number: str) -> None:
        """Store customer identity and contact details."""

        cleaned_name = name.strip()
        cleaned_contact = contact_number.strip()
        if len(cleaned_name) < 2:
            raise ValueError("customer name must contain at least two characters")
        if len(cleaned_contact) < 7:
            raise ValueError("contact number must contain at least seven characters")
        self.customer_name = cleaned_name
        self.contact_number = cleaned_contact
        self._clear_validation_and_submission()

    def apply_final_validation(
        self,
        *,
        price: PriceSnapshot,
        availability_confirmed: bool,
        validation_reference: str,
    ) -> None:
        """Store the latest TradeFlow stock and price validation."""

        reference = validation_reference.strip()
        if not reference:
            raise ValueError("validation_reference must not be empty")
        self.price_snapshot = price
        self.availability_confirmed = availability_confirmed
        self.validation_reference = reference
        self.submitted_request_id = None
        self.submitted_status = None

    def mark_submitted(self, request_id: str, status: str) -> None:
        """Remember a completed idempotent TradeFlow submission."""

        cleaned_request_id = request_id.strip()
        cleaned_status = status.strip()
        if not cleaned_request_id or not cleaned_status:
            raise ValueError("submission request_id and status must not be empty")
        if not self.ready_for_submission:
            raise ValueError("order must be ready for submission")
        self.submitted_request_id = cleaned_request_id
        self.submitted_status = cleaned_status

    def clear_product(self) -> None:
        self.product = None
        self._clear_validation_and_submission()

    def clear_quantity(self) -> None:
        self.quantity = None
        self._clear_validation_and_submission()

    def clear_fulfilment(self) -> None:
        self.fulfilment_method = None
        self.delivery_details = None
        self._clear_validation_and_submission()

    def clear_delivery_details(self) -> None:
        self.delivery_details = None
        self._clear_validation_and_submission()

    def clear_customer(self) -> None:
        self.customer_name = None
        self.contact_number = None
        self._clear_validation_and_submission()

    def clear_validation(self) -> None:
        self._clear_validation_and_submission()

    def missing_fields(self) -> tuple[str, ...]:
        """Return required information not yet collected."""

        missing: list[str] = []
        if self.product is None:
            missing.append("product")
        if self.quantity is None:
            missing.append("quantity")
        if self.fulfilment_method is None:
            missing.append("fulfilment_method")
        if self.fulfilment_method == FulfilmentMethod.DELIVERY and not self.delivery_details:
            missing.append("delivery_details")
        if not self.customer_name:
            missing.append("customer_name")
        if not self.contact_number:
            missing.append("contact_number")
        return tuple(missing)

    @property
    def ready_for_review(self) -> bool:
        return not self.missing_fields()

    @property
    def ready_for_submission(self) -> bool:
        return (
            self.ready_for_review
            and self.price_snapshot is not None
            and self.availability_confirmed
            and bool(self.validation_reference)
        )

    @property
    def submitted(self) -> bool:
        return self.submitted_request_id is not None

    @property
    def total_price(self) -> Decimal | None:
        if self.quantity is None or self.price_snapshot is None:
            return None
        return self.price_snapshot.amount * self.quantity

    def _clear_validation_and_submission(self) -> None:
        self.price_snapshot = None
        self.availability_confirmed = False
        self.validation_reference = None
        self.submitted_request_id = None
        self.submitted_status = None
