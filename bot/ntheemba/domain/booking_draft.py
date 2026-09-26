"""Typed service-booking draft and completeness rules."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, time
from decimal import Decimal
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class ServiceSelection:
    """One customer-visible TradeFlow service."""

    service_id: str
    name: str
    duration_minutes: int
    price: Decimal | None = None
    currency: str | None = None

    def __post_init__(self) -> None:
        if not self.service_id.strip():
            raise ValueError("service_id must not be empty")
        if not self.name.strip():
            raise ValueError("service name must not be empty")
        if self.duration_minutes <= 0:
            raise ValueError("duration_minutes must be greater than zero")
        if self.price is not None and self.price < 0:
            raise ValueError("price must not be negative")
        if (self.price is None) != (self.currency is None):
            raise ValueError("price and currency must be supplied together")
        if self.currency is not None:
            currency = self.currency.strip().upper()
            if len(currency) != 3:
                raise ValueError("currency must use a three-letter code")
            object.__setattr__(self, "currency", currency)


@dataclass(frozen=True, slots=True)
class AppointmentSlot:
    """One slot returned and later revalidated by TradeFlow."""

    slot_id: str
    service_id: str
    appointment_date: date
    start_time: time
    end_time: time
    staff_id: str | None = None
    staff_name: str | None = None

    def __post_init__(self) -> None:
        if not self.slot_id.strip() or not self.service_id.strip():
            raise ValueError("slot and service IDs must not be empty")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")


@dataclass(frozen=True, slots=True)
class BookingStaffOption:
    """One qualified staff choice retained inside a draft."""

    staff_id: str
    name: str

    def __post_init__(self) -> None:
        if not self.staff_id.strip() or not self.name.strip():
            raise ValueError("staff_id and name must not be empty")


@dataclass(slots=True)
class BookingDraft:
    """Mutable booking data owned by one conversation session."""

    service: ServiceSelection | None = None
    service_candidates: tuple[ServiceSelection, ...] = ()
    preferred_date: date | None = None
    selected_slot: AppointmentSlot | None = None
    available_slots: tuple[AppointmentSlot, ...] = ()
    preferred_staff_id: str | None = None
    preferred_staff_name: str | None = None
    staff_options: tuple[BookingStaffOption, ...] = ()
    customer_name: str | None = None
    contact_number: str | None = None
    slot_confirmed: bool = False
    validation_reference: str | None = None
    idempotency_key: str = field(default_factory=lambda: f"BOOKING-{uuid4()}")
    submitted_request_id: str | None = None
    submitted_status: str | None = None

    def __post_init__(self) -> None:
        if not self.idempotency_key.strip():
            raise ValueError("idempotency_key must not be empty")
        if (self.preferred_staff_id is None) != (self.preferred_staff_name is None):
            raise ValueError("preferred staff ID and name must be supplied together")
        if (self.submitted_request_id is None) != (self.submitted_status is None):
            raise ValueError("submitted_request_id and submitted_status must be supplied together")

    def set_service_candidates(self, services: tuple[ServiceSelection, ...]) -> None:
        self.service_candidates = services

    def select_service(self, service: ServiceSelection) -> None:
        self.service = service
        self.service_candidates = ()
        self.preferred_date = None
        self.selected_slot = None
        self.available_slots = ()
        self.clear_staff()
        self._clear_validation_and_submission()

    def set_preferred_date(self, preferred_date: date) -> None:
        self.preferred_date = preferred_date
        self.selected_slot = None
        self.available_slots = ()
        self.clear_staff()
        self._clear_validation_and_submission()

    def set_available_slots(self, slots: tuple[AppointmentSlot, ...]) -> None:
        if self.service is None:
            raise ValueError("a service must be selected before slots")
        for slot in slots:
            if slot.service_id != self.service.service_id:
                raise ValueError("slot does not belong to the selected service")
            if self.preferred_date is not None and slot.appointment_date != self.preferred_date:
                raise ValueError("slot does not match the preferred date")
        self.available_slots = slots
        if self.selected_slot is not None and all(
            slot.slot_id != self.selected_slot.slot_id for slot in slots
        ):
            self.selected_slot = None
            self.clear_staff()
        self._clear_validation_and_submission()

    def select_slot(self, slot: AppointmentSlot) -> None:
        if self.service is None:
            raise ValueError("a service must be selected before a slot")
        if slot.service_id != self.service.service_id:
            raise ValueError("slot does not belong to the selected service")
        if self.preferred_date is not None and slot.appointment_date != self.preferred_date:
            raise ValueError("slot does not match the preferred date")
        if self.available_slots and all(
            option.slot_id != slot.slot_id for option in self.available_slots
        ):
            raise ValueError("slot is not in the available slot options")
        self.clear_staff()
        self.preferred_date = slot.appointment_date
        self.selected_slot = slot
        if slot.staff_id is not None and slot.staff_name is not None:
            self.preferred_staff_id = slot.staff_id
            self.preferred_staff_name = slot.staff_name
        self._clear_validation_and_submission()

    def set_staff_options(self, options: tuple[BookingStaffOption, ...]) -> None:
        self.staff_options = options

    def select_staff(self, staff_id: str, name: str) -> None:
        if self.selected_slot is None:
            raise ValueError("a slot must be selected before staff")
        cleaned_id = staff_id.strip()
        cleaned_name = name.strip()
        if not cleaned_id or not cleaned_name:
            raise ValueError("staff ID and name must not be empty")
        if self.staff_options and all(
            option.staff_id != cleaned_id for option in self.staff_options
        ):
            raise ValueError("staff is not in the available staff options")
        self.preferred_staff_id = cleaned_id
        self.preferred_staff_name = cleaned_name
        self.selected_slot = replace(
            self.selected_slot,
            staff_id=cleaned_id,
            staff_name=cleaned_name,
        )
        self._clear_validation_and_submission()

    def clear_staff(self) -> None:
        self.preferred_staff_id = None
        self.preferred_staff_name = None
        self.staff_options = ()
        if self.selected_slot is not None and self.selected_slot.staff_id is not None:
            self.selected_slot = replace(
                self.selected_slot,
                staff_id=None,
                staff_name=None,
            )
        self._clear_validation_and_submission()

    def set_customer(self, name: str, contact_number: str) -> None:
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
        slot_confirmed: bool,
        validation_reference: str,
    ) -> None:
        reference = validation_reference.strip()
        if not reference:
            raise ValueError("validation_reference must not be empty")
        self.slot_confirmed = slot_confirmed
        self.validation_reference = reference
        self.submitted_request_id = None
        self.submitted_status = None

    def mark_submitted(self, request_id: str, status: str) -> None:
        cleaned_request_id = request_id.strip()
        cleaned_status = status.strip()
        if not cleaned_request_id or not cleaned_status:
            raise ValueError("submission request_id and status must not be empty")
        if not self.ready_for_submission:
            raise ValueError("booking must be ready for submission")
        self.submitted_request_id = cleaned_request_id
        self.submitted_status = cleaned_status

    def clear_service(self) -> None:
        self.service = None
        self.service_candidates = ()
        self.preferred_date = None
        self.selected_slot = None
        self.available_slots = ()
        self.clear_staff()
        self._clear_validation_and_submission()

    def clear_date(self) -> None:
        self.preferred_date = None
        self.selected_slot = None
        self.available_slots = ()
        self.clear_staff()
        self._clear_validation_and_submission()

    def clear_slot(self) -> None:
        self.selected_slot = None
        self.clear_staff()
        self._clear_validation_and_submission()

    def clear_customer(self) -> None:
        self.customer_name = None
        self.contact_number = None
        self._clear_validation_and_submission()

    def clear_validation(self) -> None:
        self._clear_validation_and_submission()

    def missing_fields(self) -> tuple[str, ...]:
        missing: list[str] = []
        if self.service is None:
            missing.append("service")
        if self.preferred_date is None:
            missing.append("preferred_date")
        if self.selected_slot is None:
            missing.append("selected_slot")
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
        return self.ready_for_review and self.slot_confirmed and bool(self.validation_reference)

    @property
    def submitted(self) -> bool:
        return self.submitted_request_id is not None

    def _clear_validation_and_submission(self) -> None:
        self.slot_confirmed = False
        self.validation_reference = None
        self.submitted_request_id = None
        self.submitted_status = None
