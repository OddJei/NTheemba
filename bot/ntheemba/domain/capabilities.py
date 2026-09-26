"""Canonical Ntheemba-owned capability catalogue and declarations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType


class Capability(StrEnum):
    """Stable capabilities understood and implemented by Ntheemba."""

    BUSINESS_INFORMATION = "business.information"
    BUSINESS_HOURS = "business.hours"
    FAQ = "faq.search"
    CLIENT_IDENTIFY = "client.identify"
    CLIENT_CREATE = "client.create"
    PRODUCT_CATALOGUE = "product.catalogue"
    PRODUCT_ORDER = "product.order"
    DELIVERY = "fulfilment.delivery"
    COLLECTION = "fulfilment.collection"
    SERVICE_CATALOGUE = "service.catalogue"
    APPOINTMENT_CREATE = "appointment.create"
    APPOINTMENT_RESCHEDULE = "appointment.reschedule"
    APPOINTMENT_CANCEL = "appointment.cancel"
    LOYALTY_READ = "loyalty.read"
    HANDOVER = "handover.create"


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    """One canonical capability and the contracts Ntheemba assigns to it."""

    capability: Capability
    title: str
    description: str
    workflow_ids: tuple[str, ...] = ()
    tradeflow_operations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.title.strip() or not self.description.strip():
            raise ValueError("capability title and description must not be empty")
        if len(set(self.workflow_ids)) != len(self.workflow_ids):
            raise ValueError("workflow_ids must be unique")
        if len(set(self.tradeflow_operations)) != len(self.tradeflow_operations):
            raise ValueError("tradeflow_operations must be unique")


@dataclass(frozen=True, slots=True)
class CapabilityDeclarationResult:
    """Validated support declaration from one business or adapter."""

    supported: frozenset[Capability]
    unknown: frozenset[str]

    @property
    def valid(self) -> bool:
        """Whether every declaration is known by Ntheemba."""

        return not self.unknown


@dataclass(frozen=True, slots=True)
class CapabilityCatalogue:
    """Closed registry controlled by Ntheemba, never by a connected business."""

    definitions: Mapping[Capability, CapabilityDefinition] = field(default_factory=dict)
    version: str = "ntheemba-capabilities-v1"

    def __post_init__(self) -> None:
        definitions = dict(self.definitions)
        if not definitions:
            raise ValueError("capability catalogue must not be empty")
        if not self.version.strip():
            raise ValueError("capability catalogue version must not be empty")
        for key, definition in definitions.items():
            if key != definition.capability:
                raise ValueError("capability definition key does not match its capability")
        object.__setattr__(self, "definitions", MappingProxyType(definitions))

    @classmethod
    def canonical(cls) -> CapabilityCatalogue:
        """Build the Phase 11.12 canonical catalogue."""

        definitions = (
            CapabilityDefinition(
                Capability.BUSINESS_INFORMATION,
                "Business information",
                "Answer approved public business profile and location questions.",
                ("information",),
                ("business.get_profile",),
            ),
            CapabilityDefinition(
                Capability.BUSINESS_HOURS,
                "Business hours",
                "Answer approved opening-hours questions.",
                ("information",),
                ("business.get_hours",),
            ),
            CapabilityDefinition(
                Capability.FAQ,
                "Frequently asked questions",
                "Search business-approved customer answers.",
                ("faq",),
                ("faq.search",),
            ),
            CapabilityDefinition(
                Capability.CLIENT_IDENTIFY,
                "Client identification",
                "Resolve a minimal business client by normalised phone number.",
                ("client",),
                ("client.find_by_phone", "client.get_minimal_profile"),
            ),
            CapabilityDefinition(
                Capability.CLIENT_CREATE,
                "Client creation",
                "Create a minimal business client after customer confirmation.",
                ("client",),
                ("client.create", "client.update_minimal_profile"),
            ),
            CapabilityDefinition(
                Capability.PRODUCT_CATALOGUE,
                "Product catalogue",
                "Search customer-visible products, prices, and availability.",
                ("catalogue",),
                (
                    "catalogue.search_products",
                    "catalogue.get_product",
                    "inventory.get_public_availability",
                ),
            ),
            CapabilityDefinition(
                Capability.PRODUCT_ORDER,
                "Product ordering",
                "Validate and submit customer product-order requests.",
                ("order",),
                ("order.validate", "order.create_request", "order.get_request_status"),
            ),
            CapabilityDefinition(
                Capability.DELIVERY,
                "Delivery fulfilment",
                "Collect and validate delivery details for an order.",
                ("order",),
                ("fulfilment.validate_delivery",),
            ),
            CapabilityDefinition(
                Capability.COLLECTION,
                "Collection fulfilment",
                "Allow the customer to collect an order from the business.",
                ("order",),
                ("fulfilment.validate_collection",),
            ),
            CapabilityDefinition(
                Capability.SERVICE_CATALOGUE,
                "Service catalogue",
                "Search customer-visible services, prices, and durations.",
                ("catalogue", "booking"),
                ("catalogue.search_services", "catalogue.get_service"),
            ),
            CapabilityDefinition(
                Capability.APPOINTMENT_CREATE,
                "Appointment creation",
                "Check availability and submit an appointment request.",
                ("booking",),
                (
                    "appointment.check_availability",
                    "appointment.get_alternatives",
                    "appointment.create_request",
                ),
            ),
            CapabilityDefinition(
                Capability.APPOINTMENT_RESCHEDULE,
                "Appointment rescheduling",
                "Request a different slot for an existing appointment.",
                ("booking",),
                ("appointment.reschedule_request",),
            ),
            CapabilityDefinition(
                Capability.APPOINTMENT_CANCEL,
                "Appointment cancellation",
                "Request cancellation of an existing appointment.",
                ("booking",),
                ("appointment.cancel_request",),
            ),
            CapabilityDefinition(
                Capability.LOYALTY_READ,
                "Loyalty status",
                "Read and explain a business-calculated loyalty result.",
                ("loyalty",),
                ("loyalty.get_status", "loyalty.get_progress"),
            ),
            CapabilityDefinition(
                Capability.HANDOVER,
                "Human handover",
                "Pause the bot and create a human-support request.",
                ("handover",),
                ("handover.create_request",),
            ),
        )
        return cls({definition.capability: definition for definition in definitions})

    def contains(self, capability: Capability | str) -> bool:
        """Return whether a capability identifier is canonical."""

        try:
            parsed = capability if isinstance(capability, Capability) else Capability(capability)
        except ValueError:
            return False
        return parsed in self.definitions

    def definition(self, capability: Capability) -> CapabilityDefinition:
        """Return one canonical definition."""

        return self.definitions[capability]

    def validate_declarations(self, declarations: Iterable[str]) -> CapabilityDeclarationResult:
        """Keep known capabilities and report all unsupported names."""

        supported: set[Capability] = set()
        unknown: set[str] = set()
        for raw in declarations:
            value = raw.strip()
            if not value:
                continue
            try:
                capability = Capability(value)
            except ValueError:
                unknown.add(value)
            else:
                if capability in self.definitions:
                    supported.add(capability)
                else:
                    unknown.add(value)
        return CapabilityDeclarationResult(frozenset(supported), frozenset(unknown))

    def known_ids(self) -> tuple[str, ...]:
        """Return sorted identifiers for diagnostics and UI display."""

        return tuple(sorted(capability.value for capability in self.definitions))
