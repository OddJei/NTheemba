"""In-memory TradeFlow implementation for workflow and application tests."""

from __future__ import annotations

from datetime import date, datetime, time
from uuid import uuid4

from ntheemba.domain.booking_draft import AppointmentSlot, ServiceSelection
from ntheemba.ports.tradeflow import (
    BookingSubmissionRequest,
    BusinessHours,
    BusinessInformation,
    BusinessProduct,
    FAQAnswer,
    OrderSubmissionRequest,
    ProductAvailability,
    StaffOption,
    SubmissionResult,
)


class InMemoryTradeFlow:
    """Seedable fake that records calls and preserves idempotency."""

    def __init__(self) -> None:
        self.businesses: dict[str, BusinessInformation] = {}
        self.hours: dict[str, BusinessHours] = {}
        self.faqs: dict[str, tuple[FAQAnswer, ...]] = {}
        self.products: dict[str, dict[str, BusinessProduct]] = {}
        self.services: dict[str, dict[str, ServiceSelection]] = {}
        self.slots: dict[tuple[str, str, date], tuple[AppointmentSlot, ...]] = {}
        self.staff: dict[
            tuple[str, str, date, time],
            tuple[StaffOption, ...],
        ] = {}
        self.orders: dict[str, SubmissionResult] = {}
        self.bookings: dict[str, SubmissionResult] = {}
        self.calls: list[tuple[str, object]] = []

    async def get_business_information(self, business_id: str) -> BusinessInformation:
        self.calls.append(("get_business_information", business_id))
        return self.businesses[business_id]

    async def get_business_hours(
        self,
        business_id: str,
        *,
        at: datetime,
    ) -> BusinessHours:
        self.calls.append(("get_business_hours", (business_id, at)))
        return self.hours[business_id]

    async def search_faqs(
        self,
        business_id: str,
        query: str,
        *,
        limit: int = 5,
    ) -> tuple[FAQAnswer, ...]:
        self.calls.append(("search_faqs", (business_id, query)))
        terms = set(query.lower().split())
        matches = [
            answer
            for answer in self.faqs.get(business_id, ())
            if not terms or terms & set(f"{answer.question} {answer.answer}".lower().split())
        ]
        return tuple(sorted(matches, key=lambda item: -item.score)[:limit])

    async def filter_business_products(
        self,
        business_id: str,
        ncpc_variant_ids: tuple[str, ...],
    ) -> tuple[BusinessProduct, ...]:
        self.calls.append(("filter_business_products", (business_id, ncpc_variant_ids)))
        wanted = set(ncpc_variant_ids)
        return tuple(
            product
            for product in self.products.get(business_id, {}).values()
            if product.ncpc_variant_id in wanted and product.public_visible
        )

    async def search_business_products(
        self,
        business_id: str,
        query: str,
        *,
        limit: int = 12,
    ) -> tuple[BusinessProduct, ...]:
        self.calls.append(("search_business_products", (business_id, query)))
        terms = tuple(token for token in query.lower().split() if token)
        matches = [
            product
            for product in self.products.get(business_id, {}).values()
            if product.public_visible
            and (
                not terms
                or all(
                    token in f"{product.name} {product.barcode or ''}".lower()
                    for token in terms
                )
            )
        ]
        return tuple(sorted(matches, key=lambda item: item.name.lower())[:limit])

    async def get_business_product(
        self,
        business_id: str,
        business_product_id: str,
    ) -> BusinessProduct | None:
        self.calls.append(("get_business_product", (business_id, business_product_id)))
        return self.products.get(business_id, {}).get(business_product_id)

    async def search_services(
        self,
        business_id: str,
        query: str,
        *,
        limit: int = 20,
    ) -> tuple[ServiceSelection, ...]:
        self.calls.append(("search_services", (business_id, query)))
        normalized = query.strip().lower()
        matches = [
            service
            for service in self.services.get(business_id, {}).values()
            if not normalized or normalized in service.name.lower()
        ]
        return tuple(sorted(matches, key=lambda item: item.name.lower())[:limit])

    async def get_service(
        self,
        business_id: str,
        service_id: str,
    ) -> ServiceSelection | None:
        self.calls.append(("get_service", (business_id, service_id)))
        return self.services.get(business_id, {}).get(service_id)

    async def check_product_availability(
        self,
        business_id: str,
        business_product_id: str,
        *,
        quantity: int,
        shop_id: str = "",
    ) -> ProductAvailability:
        self.calls.append(
            ("check_product_availability", (business_id, business_product_id, quantity, shop_id))
        )
        product = self.products[business_id][business_product_id]
        return ProductAvailability(
            business_product_id=product.business_product_id,
            requested_quantity=quantity,
            available_quantity=product.available_quantity,
            selling_price=product.selling_price,
            currency=product.currency,
            public_visible=product.public_visible,
            shop_id=shop_id or product.shop_id,
        )

    async def get_available_slots(
        self,
        business_id: str,
        service_id: str,
        *,
        appointment_date: date,
    ) -> tuple[AppointmentSlot, ...]:
        self.calls.append(("get_available_slots", (business_id, service_id, appointment_date)))
        return self.slots.get((business_id, service_id, appointment_date), ())

    async def get_qualified_staff(
        self,
        business_id: str,
        service_id: str,
        *,
        appointment_date: date,
        start_time: time,
    ) -> tuple[StaffOption, ...]:
        self.calls.append(
            (
                "get_qualified_staff",
                (business_id, service_id, appointment_date, start_time),
            )
        )
        return self.staff.get(
            (business_id, service_id, appointment_date, start_time),
            (),
        )

    async def create_order_request(
        self,
        business_id: str,
        request: OrderSubmissionRequest,
        *,
        idempotency_key: str,
    ) -> SubmissionResult:
        self.calls.append(("create_order_request", (business_id, request)))
        existing = self.orders.get(idempotency_key)
        if existing is not None:
            return SubmissionResult(
                request_id=existing.request_id,
                status=existing.status,
                created=False,
            )
        result = SubmissionResult(
            request_id=f"ORD-{uuid4()}",
            status="pending_business_confirmation",
            created=True,
        )
        self.orders[idempotency_key] = result
        return result

    async def create_booking_request(
        self,
        business_id: str,
        request: BookingSubmissionRequest,
        *,
        idempotency_key: str,
    ) -> SubmissionResult:
        self.calls.append(("create_booking_request", (business_id, request)))
        existing = self.bookings.get(idempotency_key)
        if existing is not None:
            return SubmissionResult(
                request_id=existing.request_id,
                status=existing.status,
                created=False,
            )
        result = SubmissionResult(
            request_id=f"BKG-{uuid4()}",
            status="pending_business_confirmation",
            created=True,
        )
        self.bookings[idempotency_key] = result
        return result
