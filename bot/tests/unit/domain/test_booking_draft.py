"""Tests for booking draft completeness and slot rules."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest
from ntheemba.domain.booking_draft import (
    AppointmentSlot,
    BookingDraft,
    BookingStaffOption,
    ServiceSelection,
)


def _service() -> ServiceSelection:
    return ServiceSelection(
        service_id="SVC-001",
        name="Knotless Braids",
        duration_minutes=180,
        price=Decimal("350"),
        currency="ZMW",
    )


def _slot(service_id: str = "SVC-001") -> AppointmentSlot:
    return AppointmentSlot(
        slot_id="SLOT-001",
        service_id=service_id,
        appointment_date=date(2026, 7, 25),
        start_time=time(9, 0),
        end_time=time(12, 0),
        staff_id="STAFF-001",
    )


def test_booking_rejects_slot_for_another_service() -> None:
    draft = BookingDraft()
    draft.select_service(_service())

    with pytest.raises(ValueError, match="selected service"):
        draft.select_slot(_slot(service_id="SVC-OTHER"))


def test_booking_requires_final_slot_validation_before_submission() -> None:
    draft = BookingDraft()
    draft.select_service(_service())
    draft.set_preferred_date(date(2026, 7, 25))
    draft.select_slot(_slot())
    draft.set_customer("Mary", "260971111111")

    assert draft.ready_for_review
    assert not draft.ready_for_submission

    draft.apply_final_validation(slot_confirmed=True, validation_reference="BOOK-VAL-001")

    assert draft.ready_for_submission


def test_booking_mutation_invalidates_validation_and_submission() -> None:
    draft = BookingDraft()
    service = _service()
    slot = _slot()
    draft.select_service(service)
    draft.set_preferred_date(date(2026, 7, 25))
    draft.set_available_slots((slot,))
    draft.select_slot(slot)
    draft.set_customer("Mary", "260971111111")
    draft.apply_final_validation(slot_confirmed=True, validation_reference="VAL-1")
    draft.mark_submitted("BKG-1", "pending")

    draft.set_customer("Mary Banda", "260971111111")

    assert not draft.slot_confirmed
    assert draft.validation_reference is None
    assert not draft.submitted


def test_staff_selection_updates_selected_slot() -> None:
    draft = BookingDraft()
    service = _service()
    slot = _slot()
    draft.select_service(service)
    draft.set_preferred_date(date(2026, 7, 25))
    draft.set_available_slots((slot,))
    draft.select_slot(slot)
    draft.set_staff_options((BookingStaffOption("STAFF-1", "Mary"),))

    draft.select_staff("STAFF-1", "Mary")

    assert draft.preferred_staff_id == "STAFF-1"
    assert draft.selected_slot is not None
    assert draft.selected_slot.staff_name == "Mary"
