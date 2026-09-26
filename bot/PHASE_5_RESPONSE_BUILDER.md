# Phase 5 — Central Response Builder

Phase 5 adds one pure presentation service for customer-facing replies.

## Added module

```text
ntheemba/services/
└── response_builder.py
```

## Purpose

`ResponseBuilder` converts approved domain objects and customer-safe port DTOs
into `WorkflowReply` objects. It performs no storage, HTTP, Redis, queue, model,
or workflow-state operations.

## Supported responses

- business information;
- business hours and special closures;
- approved FAQ answers and no-match fallback;
- numbered product and service results;
- product and service details;
- optional product image replies;
- product clarification and strong-match confirmation;
- unavailable quantities;
- appointment slots and qualified staff;
- order and booking reviews;
- missing-field prompts;
- corrections;
- order and booking submission confirmations;
- cancellation;
- human handover and bot resume;
- retryable and non-retryable dependency failures;
- generic clarification and failure replies.

## Safety decisions

- Internal NCPC, TradeFlow, slot, staff, and validation IDs are never printed.
- Only submission request references intended for the customer are displayed.
- Business products must be public before appearing in result lists.
- Images must use public HTTP or HTTPS URLs.
- Control characters are removed from external text.
- Message length is bounded.
- Money uses `Decimal`; no floating-point conversion is used.
- The builder raises `ResponseBuilderError` rather than inventing missing review data.
- The builder never mutates `OrderDraft`, `BookingDraft`, `Session`, or resolution objects.

## Workflow usage example

```python
reply = response_builder.order_review(session.order_draft)
return WorkflowResult(replies=(reply,))
```

## Run Phase 5 checks

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy ntheemba tests
```

## Next phase

Phase 6 builds the first real workflow:

```text
workflows/
└── information.py
```

It will use `TradeFlowPort` and `ResponseBuilder` to handle business information,
hours, approved FAQs, and safe side-question interruption/resume.
