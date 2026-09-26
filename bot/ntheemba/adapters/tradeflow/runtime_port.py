"""Integration-selected TradeFlowPort implementation for workflow calls."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, time

from ntheemba.adapters.tradeflow.factory import TradeFlowPortFactory
from ntheemba.application.runtime_context import current_runtime_context
from ntheemba.domain.booking_draft import AppointmentSlot, ServiceSelection
from ntheemba.domain.capabilities import Capability
from ntheemba.domain.customers import LoyaltyStatus, MinimalBusinessClient
from ntheemba.ports.tradeflow import (
    BookingSubmissionRequest,
    BusinessHours,
    BusinessInformation,
    BusinessProduct,
    FAQAnswer,
    MinimalClientCreateRequest,
    OrderSubmissionRequest,
    ProductAvailability,
    StaffOption,
    SubmissionResult,
    TradeFlowPort,
)


class RuntimeIntegrationUnavailableError(LookupError):
    """Raised when workflow execution has no configured integration."""


class DynamicTradeFlowPort:
    """Route generic workflow TradeFlow calls through configured integrations."""

    def __init__(
        self,
        ports: Mapping[str, TradeFlowPort] | None = None,
        *,
        factory: TradeFlowPortFactory | None = None,
    ) -> None:
        if not ports and factory is None:
            raise ValueError("ports or factory must be configured")
        self._ports = dict(ports or {})
        self._factory = factory

    def _port(self, business_id: str, capability: Capability) -> TradeFlowPort:
        context = current_runtime_context()
        if context is None:
            raise RuntimeIntegrationUnavailableError(
                "No resolved business context is bound for this TradeFlow call."
            )
        if business_id != context.business.business_id:
            raise RuntimeIntegrationUnavailableError(
                "TradeFlow call business does not match the resolved channel."
            )
        if capability not in context.capabilities:
            raise RuntimeIntegrationUnavailableError(
                "The resolved business has not enabled this capability."
            )
        integration = context.integration_for(capability)
        if integration is None:
            raise RuntimeIntegrationUnavailableError(
                "No enabled integration is configured for this capability."
            )
        port = self._ports.get(integration.adapter_type)
        if port is not None:
            return port
        if self._factory is not None:
            return self._factory.build(integration)
        raise RuntimeIntegrationUnavailableError(
            f"No TradeFlow port is registered for {integration.adapter_type!r}."
        )

    async def get_business_information(self, business_id: str) -> BusinessInformation:
        port = self._port(business_id, Capability.BUSINESS_INFORMATION)
        return await port.get_business_information(business_id)

    async def get_business_hours(
        self,
        business_id: str,
        *,
        at: datetime,
    ) -> BusinessHours:
        port = self._port(business_id, Capability.BUSINESS_HOURS)
        return await port.get_business_hours(business_id, at=at)

    async def search_faqs(
        self,
        business_id: str,
        query: str,
        *,
        limit: int = 5,
    ) -> tuple[FAQAnswer, ...]:
        port = self._port(business_id, Capability.FAQ)
        return await port.search_faqs(business_id, query, limit=limit)

    async def filter_business_products(
        self,
        business_id: str,
        ncpc_variant_ids: tuple[str, ...],
    ) -> tuple[BusinessProduct, ...]:
        port = self._port(business_id, Capability.PRODUCT_CATALOGUE)
        return await port.filter_business_products(business_id, ncpc_variant_ids)

    async def search_business_products(
        self,
        business_id: str,
        query: str,
        *,
        limit: int = 12,
    ) -> tuple[BusinessProduct, ...]:
        port = self._port(business_id, Capability.PRODUCT_CATALOGUE)
        return await port.search_business_products(business_id, query, limit=limit)

    async def get_business_product(
        self,
        business_id: str,
        business_product_id: str,
    ) -> BusinessProduct | None:
        port = self._port(business_id, Capability.PRODUCT_CATALOGUE)
        return await port.get_business_product(business_id, business_product_id)

    async def search_services(
        self,
        business_id: str,
        query: str,
        *,
        limit: int = 20,
    ) -> tuple[ServiceSelection, ...]:
        port = self._port(business_id, Capability.SERVICE_CATALOGUE)
        return await port.search_services(business_id, query, limit=limit)

    async def get_service(
        self,
        business_id: str,
        service_id: str,
    ) -> ServiceSelection | None:
        port = self._port(business_id, Capability.SERVICE_CATALOGUE)
        return await port.get_service(business_id, service_id)

    async def find_client_by_phone(
        self,
        business_id: str,
        phone_e164: str,
    ) -> MinimalBusinessClient | None:
        port = self._port(business_id, Capability.CLIENT_IDENTIFY)
        return await port.find_client_by_phone(business_id, phone_e164)

    async def create_minimal_client(
        self,
        business_id: str,
        request: MinimalClientCreateRequest,
        *,
        idempotency_key: str,
    ) -> MinimalBusinessClient:
        port = self._port(business_id, Capability.CLIENT_CREATE)
        return await port.create_minimal_client(
            business_id,
            request,
            idempotency_key=idempotency_key,
        )

    async def get_loyalty_status(
        self,
        business_id: str,
        client_id: str,
    ) -> LoyaltyStatus | None:
        port = self._port(business_id, Capability.LOYALTY_READ)
        return await port.get_loyalty_status(business_id, client_id)

    async def check_product_availability(
        self,
        business_id: str,
        business_product_id: str,
        *,
        quantity: int,
        shop_id: str = "",
    ) -> ProductAvailability:
        port = self._port(business_id, Capability.PRODUCT_CATALOGUE)
        return await port.check_product_availability(
            business_id,
            business_product_id,
            quantity=quantity,
            shop_id=shop_id,
        )

    async def get_available_slots(
        self,
        business_id: str,
        service_id: str,
        *,
        appointment_date: date,
    ) -> tuple[AppointmentSlot, ...]:
        port = self._port(business_id, Capability.APPOINTMENT_CREATE)
        return await port.get_available_slots(
            business_id,
            service_id,
            appointment_date=appointment_date,
        )

    async def get_qualified_staff(
        self,
        business_id: str,
        service_id: str,
        *,
        appointment_date: date,
        start_time: time,
    ) -> tuple[StaffOption, ...]:
        port = self._port(business_id, Capability.APPOINTMENT_CREATE)
        return await port.get_qualified_staff(
            business_id,
            service_id,
            appointment_date=appointment_date,
            start_time=start_time,
        )

    async def create_order_request(
        self,
        business_id: str,
        request: OrderSubmissionRequest,
        *,
        idempotency_key: str,
    ) -> SubmissionResult:
        port = self._port(business_id, Capability.PRODUCT_ORDER)
        return await port.create_order_request(
            business_id,
            request,
            idempotency_key=idempotency_key,
        )

    async def create_booking_request(
        self,
        business_id: str,
        request: BookingSubmissionRequest,
        *,
        idempotency_key: str,
    ) -> SubmissionResult:
        port = self._port(business_id, Capability.APPOINTMENT_CREATE)
        return await port.create_booking_request(
            business_id,
            request,
            idempotency_key=idempotency_key,
        )
