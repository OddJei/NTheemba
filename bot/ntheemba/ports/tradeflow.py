"""Port and public DTOs for business-specific TradeFlow facts and actions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Protocol

from ntheemba.domain.booking_draft import AppointmentSlot, ServiceSelection
from ntheemba.domain.customers import LoyaltyStatus, MinimalBusinessClient
from ntheemba.domain.enums import FulfilmentMethod


@dataclass(frozen=True, slots=True)
class BusinessInformation:
    """Customer-safe public information for one business."""

    business_id: str
    name: str
    description: str = ""
    location: str = ""
    contact_phone: str = ""
    currency: str = "ZMW"

    def __post_init__(self) -> None:
        if not self.business_id.strip() or not self.name.strip():
            raise ValueError("business_id and name must not be empty")
        currency = self.currency.strip().upper()
        if len(currency) != 3:
            raise ValueError("currency must use a three-letter code")
        object.__setattr__(self, "currency", currency)


@dataclass(frozen=True, slots=True)
class BusinessHours:
    """Opening status at one requested moment."""

    is_open: bool
    local_date: date
    opens_at: time | None = None
    closes_at: time | None = None
    special_closure: bool = False
    note: str = ""

    def __post_init__(self) -> None:
        if (self.opens_at is None) != (self.closes_at is None):
            raise ValueError("opens_at and closes_at must be supplied together")


@dataclass(frozen=True, slots=True)
class FAQAnswer:
    """One approved business FAQ answer."""

    faq_id: str
    question: str
    answer: str
    score: float = 1.0

    def __post_init__(self) -> None:
        if not self.faq_id.strip() or not self.answer.strip():
            raise ValueError("faq_id and answer must not be empty")
        if not 0 <= self.score <= 1:
            raise ValueError("score must be between zero and one")


@dataclass(frozen=True, slots=True)
class BusinessProduct:
    """Product facts owned by one TradeFlow business.

    NCPC identifiers are optional for provisional within-business visibility.  A linked
    product remains canonical/trusted; an awaiting-review product may be surfaced only
    under Ntheemba's explicit fallback policy and must never receive invented NCPC IDs.
    """

    business_product_id: str
    ncpc_product_id: str | None
    name: str
    selling_price: Decimal
    currency: str
    available_quantity: int
    ncpc_variant_id: str | None = None
    public_visible: bool = True
    image_url: str | None = None
    barcode: str | None = None
    shop_id: str = ""
    identity_status: str = "linked"
    catalogue_source: str = "tradeflow_local_catalogue"

    def __post_init__(self) -> None:
        if not self.business_product_id.strip():
            raise ValueError("business_product_id must not be empty")
        status = self.identity_status.strip().lower() or "local_only"
        object.__setattr__(self, "identity_status", status)
        if self.ncpc_product_id is not None:
            product_id = self.ncpc_product_id.strip()
            object.__setattr__(self, "ncpc_product_id", product_id or None)
        if self.ncpc_variant_id is None and self.ncpc_product_id is not None:
            object.__setattr__(self, "ncpc_variant_id", self.ncpc_product_id)
        elif self.ncpc_variant_id is not None:
            variant_id = self.ncpc_variant_id.strip()
            object.__setattr__(self, "ncpc_variant_id", variant_id or None)
        if status == "linked" and (not self.ncpc_product_id or not self.ncpc_variant_id):
            raise ValueError("linked products require NCPC product and variant IDs")
        if not self.name.strip():
            raise ValueError("name must not be empty")
        if self.selling_price < 0:
            raise ValueError("selling_price must not be negative")
        if self.available_quantity < 0:
            raise ValueError("available_quantity must not be negative")
        currency = self.currency.strip().upper()
        if len(currency) != 3:
            raise ValueError("currency must use a three-letter code")
        object.__setattr__(self, "currency", currency)

    @property
    def available(self) -> bool:
        """Whether the product is visible and has positive available stock."""

        return self.public_visible and self.available_quantity > 0

    @property
    def trusted_identity(self) -> bool:
        """Whether NCPC has supplied the canonical product/variant identity."""

        return (
            self.identity_status == "linked"
            and self.ncpc_product_id is not None
            and self.ncpc_variant_id is not None
        )


@dataclass(frozen=True, slots=True)
class ProductAvailability:
    """Result of checking a requested product quantity."""

    business_product_id: str
    requested_quantity: int
    available_quantity: int
    selling_price: Decimal
    currency: str
    public_visible: bool = True
    shop_id: str = ""

    def __post_init__(self) -> None:
        if not self.business_product_id.strip():
            raise ValueError("business_product_id must not be empty")
        if self.requested_quantity <= 0:
            raise ValueError("requested_quantity must be greater than zero")
        if self.available_quantity < 0:
            raise ValueError("available_quantity must not be negative")
        if self.selling_price < 0:
            raise ValueError("selling_price must not be negative")
        currency = self.currency.strip().upper()
        if len(currency) != 3:
            raise ValueError("currency must use a three-letter code")
        object.__setattr__(self, "currency", currency)

    @property
    def available(self) -> bool:
        """Whether the exact requested quantity may proceed."""

        return self.public_visible and self.available_quantity >= self.requested_quantity


@dataclass(frozen=True, slots=True)
class StaffOption:
    """Qualified staff member available for a service slot."""

    staff_id: str
    name: str

    def __post_init__(self) -> None:
        if not self.staff_id.strip() or not self.name.strip():
            raise ValueError("staff_id and name must not be empty")


@dataclass(frozen=True, slots=True)
class OrderSubmissionRequest:
    """Validated order request sent to TradeFlow."""

    business_product_id: str
    quantity: int
    fulfilment_method: FulfilmentMethod
    customer_name: str
    contact_number: str
    delivery_details: str = ""
    shop_id: str = ""

    def __post_init__(self) -> None:
        if not self.business_product_id.strip():
            raise ValueError("business_product_id must not be empty")
        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        if len(self.customer_name.strip()) < 2:
            raise ValueError("customer_name is invalid")
        if len(self.contact_number.strip()) < 7:
            raise ValueError("contact_number is invalid")
        if self.fulfilment_method == FulfilmentMethod.DELIVERY:
            if len(self.delivery_details.strip()) < 5:
                raise ValueError("delivery orders require delivery_details")


@dataclass(frozen=True, slots=True)
class BookingSubmissionRequest:
    """Validated booking request sent to TradeFlow."""

    service_id: str
    slot_id: str
    appointment_date: date
    start_time: time
    customer_name: str
    contact_number: str
    staff_id: str | None = None

    def __post_init__(self) -> None:
        if not self.service_id.strip() or not self.slot_id.strip():
            raise ValueError("service_id and slot_id must not be empty")
        if len(self.customer_name.strip()) < 2:
            raise ValueError("customer_name is invalid")
        if len(self.contact_number.strip()) < 7:
            raise ValueError("contact_number is invalid")


@dataclass(frozen=True, slots=True)
class SubmissionResult:
    """Identifier returned after idempotent request creation."""

    request_id: str
    status: str
    created: bool

    def __post_init__(self) -> None:
        if not self.request_id.strip() or not self.status.strip():
            raise ValueError("request_id and status must not be empty")


@dataclass(frozen=True, slots=True)
class MinimalClientCreateRequest:
    """Minimal client details Ntheemba may send after customer confirmation."""

    display_name: str
    phone_e164: str

    def __post_init__(self) -> None:
        if len(self.display_name.strip()) < 2:
            raise ValueError("display_name is invalid")
        if not self.phone_e164.startswith("+"):
            raise ValueError("phone_e164 must use international + notation")


class TradeFlowPort(Protocol):
    """Business-specific facts and transaction operations."""

    async def get_business_information(self, business_id: str) -> BusinessInformation:
        """Return customer-safe business information."""

    async def get_business_hours(
        self,
        business_id: str,
        *,
        at: datetime,
    ) -> BusinessHours:
        """Return opening status at the requested time."""

    async def search_faqs(
        self,
        business_id: str,
        query: str,
        *,
        limit: int = 5,
    ) -> tuple[FAQAnswer, ...]:
        """Search approved FAQ answers."""

    async def filter_business_products(
        self,
        business_id: str,
        ncpc_variant_ids: tuple[str, ...],
    ) -> tuple[BusinessProduct, ...]:
        """Return visible products sold by this business for NCPC variant IDs."""

    async def search_business_products(
        self,
        business_id: str,
        query: str,
        *,
        limit: int = 12,
    ) -> tuple[BusinessProduct, ...]:
        """Search the same tenant's local catalogue for controlled fallback resolution."""

    async def get_business_product(
        self,
        business_id: str,
        business_product_id: str,
    ) -> BusinessProduct | None:
        """Return one business product."""

    async def search_services(
        self,
        business_id: str,
        query: str,
        *,
        limit: int = 20,
    ) -> tuple[ServiceSelection, ...]:
        """Search customer-visible services."""

    async def get_service(
        self,
        business_id: str,
        service_id: str,
    ) -> ServiceSelection | None:
        """Return one customer-visible service."""

    async def find_client_by_phone(
        self,
        business_id: str,
        phone_e164: str,
    ) -> MinimalBusinessClient | None:
        """Return a minimal business client when this capability is enabled."""

    async def create_minimal_client(
        self,
        business_id: str,
        request: MinimalClientCreateRequest,
        *,
        idempotency_key: str,
    ) -> MinimalBusinessClient:
        """Create a minimal business client idempotently."""

    async def get_loyalty_status(
        self,
        business_id: str,
        client_id: str,
    ) -> LoyaltyStatus | None:
        """Return a business-calculated loyalty result."""

    async def check_product_availability(
        self,
        business_id: str,
        business_product_id: str,
        *,
        quantity: int,
        shop_id: str = "",
    ) -> ProductAvailability:
        """Revalidate product visibility, price, and quantity."""

    async def get_available_slots(
        self,
        business_id: str,
        service_id: str,
        *,
        appointment_date: date,
    ) -> tuple[AppointmentSlot, ...]:
        """Return available service slots."""

    async def get_qualified_staff(
        self,
        business_id: str,
        service_id: str,
        *,
        appointment_date: date,
        start_time: time,
    ) -> tuple[StaffOption, ...]:
        """Return qualified staff for the selected time."""

    async def create_order_request(
        self,
        business_id: str,
        request: OrderSubmissionRequest,
        *,
        idempotency_key: str,
    ) -> SubmissionResult:
        """Create an idempotent order request."""

    async def create_booking_request(
        self,
        business_id: str,
        request: BookingSubmissionRequest,
        *,
        idempotency_key: str,
    ) -> SubmissionResult:
        """Create an idempotent booking request."""
