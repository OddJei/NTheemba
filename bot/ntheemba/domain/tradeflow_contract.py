"""Ntheemba-owned TradeFlow operation catalogue and versioned envelopes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from ntheemba.domain.capabilities import Capability


class TradeFlowOperation(StrEnum):
    """Operations Ntheemba explicitly understands and may invoke."""

    BUSINESS_GET_PROFILE = "business.get_profile"
    BUSINESS_GET_HOURS = "business.get_hours"
    FAQ_SEARCH = "faq.search"
    CLIENT_FIND_BY_PHONE = "client.find_by_phone"
    CLIENT_GET_MINIMAL_PROFILE = "client.get_minimal_profile"
    CLIENT_CREATE = "client.create"
    CLIENT_UPDATE_MINIMAL_PROFILE = "client.update_minimal_profile"
    CATALOGUE_SEARCH_PRODUCTS = "catalogue.search_products"
    CATALOGUE_GET_PRODUCT = "catalogue.get_product"
    INVENTORY_GET_PUBLIC_AVAILABILITY = "inventory.get_public_availability"
    ORDER_VALIDATE = "order.validate"
    ORDER_CREATE_REQUEST = "order.create_request"
    ORDER_GET_REQUEST_STATUS = "order.get_request_status"
    FULFILMENT_VALIDATE_DELIVERY = "fulfilment.validate_delivery"
    FULFILMENT_VALIDATE_COLLECTION = "fulfilment.validate_collection"
    CATALOGUE_SEARCH_SERVICES = "catalogue.search_services"
    CATALOGUE_GET_SERVICE = "catalogue.get_service"
    APPOINTMENT_CHECK_AVAILABILITY = "appointment.check_availability"
    APPOINTMENT_GET_ALTERNATIVES = "appointment.get_alternatives"
    APPOINTMENT_CREATE_REQUEST = "appointment.create_request"
    APPOINTMENT_RESCHEDULE_REQUEST = "appointment.reschedule_request"
    APPOINTMENT_CANCEL_REQUEST = "appointment.cancel_request"
    LOYALTY_GET_STATUS = "loyalty.get_status"
    LOYALTY_GET_PROGRESS = "loyalty.get_progress"
    HANDOVER_CREATE_REQUEST = "handover.create_request"


_OPERATION_CAPABILITIES: Mapping[TradeFlowOperation, Capability] = MappingProxyType(
    {
        TradeFlowOperation.BUSINESS_GET_PROFILE: Capability.BUSINESS_INFORMATION,
        TradeFlowOperation.BUSINESS_GET_HOURS: Capability.BUSINESS_HOURS,
        TradeFlowOperation.FAQ_SEARCH: Capability.FAQ,
        TradeFlowOperation.CLIENT_FIND_BY_PHONE: Capability.CLIENT_IDENTIFY,
        TradeFlowOperation.CLIENT_GET_MINIMAL_PROFILE: Capability.CLIENT_IDENTIFY,
        TradeFlowOperation.CLIENT_CREATE: Capability.CLIENT_CREATE,
        TradeFlowOperation.CLIENT_UPDATE_MINIMAL_PROFILE: Capability.CLIENT_CREATE,
        TradeFlowOperation.CATALOGUE_SEARCH_PRODUCTS: Capability.PRODUCT_CATALOGUE,
        TradeFlowOperation.CATALOGUE_GET_PRODUCT: Capability.PRODUCT_CATALOGUE,
        TradeFlowOperation.INVENTORY_GET_PUBLIC_AVAILABILITY: Capability.PRODUCT_CATALOGUE,
        TradeFlowOperation.ORDER_VALIDATE: Capability.PRODUCT_ORDER,
        TradeFlowOperation.ORDER_CREATE_REQUEST: Capability.PRODUCT_ORDER,
        TradeFlowOperation.ORDER_GET_REQUEST_STATUS: Capability.PRODUCT_ORDER,
        TradeFlowOperation.FULFILMENT_VALIDATE_DELIVERY: Capability.DELIVERY,
        TradeFlowOperation.FULFILMENT_VALIDATE_COLLECTION: Capability.COLLECTION,
        TradeFlowOperation.CATALOGUE_SEARCH_SERVICES: Capability.SERVICE_CATALOGUE,
        TradeFlowOperation.CATALOGUE_GET_SERVICE: Capability.SERVICE_CATALOGUE,
        TradeFlowOperation.APPOINTMENT_CHECK_AVAILABILITY: Capability.APPOINTMENT_CREATE,
        TradeFlowOperation.APPOINTMENT_GET_ALTERNATIVES: Capability.APPOINTMENT_CREATE,
        TradeFlowOperation.APPOINTMENT_CREATE_REQUEST: Capability.APPOINTMENT_CREATE,
        TradeFlowOperation.APPOINTMENT_RESCHEDULE_REQUEST: Capability.APPOINTMENT_RESCHEDULE,
        TradeFlowOperation.APPOINTMENT_CANCEL_REQUEST: Capability.APPOINTMENT_CANCEL,
        TradeFlowOperation.LOYALTY_GET_STATUS: Capability.LOYALTY_READ,
        TradeFlowOperation.LOYALTY_GET_PROGRESS: Capability.LOYALTY_READ,
        TradeFlowOperation.HANDOVER_CREATE_REQUEST: Capability.HANDOVER,
    }
)


class UnknownTradeFlowOperationError(LookupError):
    """Raised when an adapter proposes a method Ntheemba has not defined."""


class InvalidTradeFlowRequestError(ValueError):
    """Raised when a known operation lacks required public contract fields."""


@dataclass(frozen=True, slots=True)
class TradeFlowRequest:
    """Versioned, tenant-bound request sent through a TradeFlow adapter."""

    request_id: str
    business_id: str
    operation: TradeFlowOperation
    payload: Mapping[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""
    schema_version: str = "tradeflow.ntheemba.v1"

    def __post_init__(self) -> None:
        if not self.request_id.strip() or not self.business_id.strip():
            raise ValueError("request_id and business_id must not be empty")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


@dataclass(frozen=True, slots=True)
class TradeFlowResponse:
    """Validated adapter response that never exposes raw application state."""

    request_id: str
    business_id: str
    ok: bool
    data: Mapping[str, Any] = field(default_factory=dict)
    error_code: str = ""
    error_message: str = ""
    schema_version: str = "tradeflow.ntheemba.v1"

    def __post_init__(self) -> None:
        if not self.request_id.strip() or not self.business_id.strip():
            raise ValueError("request_id and business_id must not be empty")
        if self.ok and (self.error_code or self.error_message):
            raise ValueError("successful responses cannot contain errors")
        if not self.ok and not self.error_code.strip():
            raise ValueError("failed responses require error_code")
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))


def parse_tradeflow_operation(value: str) -> TradeFlowOperation:
    """Parse an operation only when Ntheemba owns its definition."""

    try:
        return TradeFlowOperation(value)
    except ValueError as error:
        raise UnknownTradeFlowOperationError(
            f"TradeFlow operation {value!r} is not known by Ntheemba"
        ) from error


def capability_for_operation(operation: TradeFlowOperation) -> Capability:
    """Return the canonical capability required for an operation."""

    return _OPERATION_CAPABILITIES[operation]


_REQUIRED_PAYLOAD_FIELDS: Mapping[TradeFlowOperation, frozenset[str]] = MappingProxyType(
    {
        TradeFlowOperation.BUSINESS_GET_PROFILE: frozenset(),
        TradeFlowOperation.BUSINESS_GET_HOURS: frozenset({"at"}),
        TradeFlowOperation.FAQ_SEARCH: frozenset({"query"}),
        TradeFlowOperation.CLIENT_FIND_BY_PHONE: frozenset({"phone_e164"}),
        TradeFlowOperation.CLIENT_GET_MINIMAL_PROFILE: frozenset({"client_id"}),
        TradeFlowOperation.CLIENT_CREATE: frozenset({"display_name", "phone_e164"}),
        TradeFlowOperation.CLIENT_UPDATE_MINIMAL_PROFILE: frozenset({"client_id"}),
        TradeFlowOperation.CATALOGUE_SEARCH_PRODUCTS: frozenset(),
        TradeFlowOperation.CATALOGUE_GET_PRODUCT: frozenset({"business_product_id"}),
        TradeFlowOperation.INVENTORY_GET_PUBLIC_AVAILABILITY: frozenset(
            {"business_product_id", "quantity"}
        ),
        TradeFlowOperation.ORDER_VALIDATE: frozenset(
            {"business_product_id", "quantity", "fulfilment_method"}
        ),
        TradeFlowOperation.ORDER_CREATE_REQUEST: frozenset(
            {
                "business_product_id",
                "quantity",
                "fulfilment_method",
                "customer_name",
                "contact_number",
            }
        ),
        TradeFlowOperation.ORDER_GET_REQUEST_STATUS: frozenset({"request_id"}),
        TradeFlowOperation.FULFILMENT_VALIDATE_DELIVERY: frozenset({"delivery_details"}),
        TradeFlowOperation.FULFILMENT_VALIDATE_COLLECTION: frozenset(),
        TradeFlowOperation.CATALOGUE_SEARCH_SERVICES: frozenset({"query"}),
        TradeFlowOperation.CATALOGUE_GET_SERVICE: frozenset({"service_id"}),
        TradeFlowOperation.APPOINTMENT_CHECK_AVAILABILITY: frozenset(
            {"service_id", "date"}
        ),
        TradeFlowOperation.APPOINTMENT_GET_ALTERNATIVES: frozenset(
            {"service_id", "date"}
        ),
        TradeFlowOperation.APPOINTMENT_CREATE_REQUEST: frozenset(
            {
                "service_id",
                "slot_id",
                "appointment_date",
                "start_time",
                "customer_name",
                "contact_number",
            }
        ),
        TradeFlowOperation.APPOINTMENT_RESCHEDULE_REQUEST: frozenset(
            {"request_id", "slot_id"}
        ),
        TradeFlowOperation.APPOINTMENT_CANCEL_REQUEST: frozenset({"request_id"}),
        TradeFlowOperation.LOYALTY_GET_STATUS: frozenset({"client_id"}),
        TradeFlowOperation.LOYALTY_GET_PROGRESS: frozenset({"client_id"}),
        TradeFlowOperation.HANDOVER_CREATE_REQUEST: frozenset({"summary"}),
    }
)


def required_payload_fields(operation: TradeFlowOperation) -> frozenset[str]:
    """Return public contract fields that must be present before adapter execution."""

    return _REQUIRED_PAYLOAD_FIELDS[operation]


def validate_required_payload(request: TradeFlowRequest) -> None:
    """Fail closed when a known operation lacks required input fields."""

    missing = tuple(
        field
        for field in sorted(required_payload_fields(request.operation))
        if _missing_payload_value(request.payload.get(field))
    )
    if missing:
        joined = ", ".join(missing)
        raise InvalidTradeFlowRequestError(
            f"{request.operation.value!r} requires payload field(s): {joined}"
        )


def _missing_payload_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (tuple, list, set, frozenset, dict)):
        return not value
    return False
