# Phase 11 — Booking Workflow

Phase 11 completes the service-booking conversation workflow.

## Added files

```text
ntheemba/workflows/booking.py
tests/unit/workflows/test_booking.py
tests/unit/application/test_booking_integration.py
```

## Flow

```text
IDLE / START
  → BOOKING / SERVICE_SELECTION
  → PREFERRED_DATE
  → TIME_SELECTION
  → optional STAFF_SELECTION
  → CUSTOMER_DETAILS
  → BOOKING_REVIEW
  → SUBMITTING
  → SUBMITTED
```

## Guarantees

- Services, slots, staff, price, and availability come only from TradeFlow.
- Past dates are rejected.
- Staff choice is optional; `SKIP` means no preference.
- The selected slot is re-read immediately before review and confirmation.
- A disappeared slot returns the customer to current alternatives.
- A changed service price requires fresh confirmation.
- Booking submission uses a stable idempotency key and stores the result for replay.
- Corrections invalidate prior validation and preserve unrelated fields.
- No payment is taken by Ntheemba.

## Checks

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy ntheemba tests
```

## Next phase

Phase 12 adds Redis session, lock, and deduplication adapters.
