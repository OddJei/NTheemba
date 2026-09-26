# Phase 6 — Information and FAQ Workflow

Phase 6 introduces the first production-shaped workflow handler.

## Added files

```text
ntheemba/workflows/
├── __init__.py
└── information.py

tests/unit/workflows/
└── test_information.py
```

## Owned intents

The workflow owns:

- `BUSINESS_INFO`
- `BUSINESS_HOURS`
- `FAQ`

Use `build_information_routes(workflow)` to register all three intents with
`WorkflowRouter`.

## Direct request flow

```text
IDLE / START
    ↓
INFORMATION / INFORMATION_LOOKUP
or FAQ / FAQ_SEARCH
    ↓
TradeFlow public data
    ↓
ResponseBuilder
    ↓
IDLE / START
```

## Safe interruption flow

```text
ORDER, BOOKING, or CATALOGUE workflow
    ↓
Preserve flow, stage, and pending question
    ↓
INFORMATION or FAQ state
    ↓
Answer the side question
    ↓
Restore the exact prior workflow
    ↓
Repeat the pending question
```

Example:

```text
Ntheemba: How many would you like?
Customer: What time do you close?
Ntheemba: Yes, the business is open now and closes at 18:00.
Ntheemba: Back to your previous request: How many would you like?
```

## Dependency behavior

Expected business-service failures are converted into customer-safe replies:

- `ConnectionError` and `TimeoutError` are marked retryable.
- `LookupError`, including a missing business configuration, is marked
  non-retryable.
- Error type is audited, but raw exception text is not exposed.
- An interrupted order, booking, or catalogue workflow is restored even when
  the information lookup fails.

Unexpected programming errors are not swallowed. They continue to the Phase 3
application rollback and generic-failure boundary.

## Safety guarantees

- Only customer-safe `TradeFlowPort` DTOs reach `ResponseBuilder`.
- FAQ answers come only from approved TradeFlow records.
- The workflow does not invent opening hours or business facts.
- Internal FAQ IDs and business identifiers are not sent to the customer.
- Direct information requests leave no temporary information state behind.
- Side questions do not destroy product, order, booking, or pending-question
  state.

## Run checks

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy ntheemba tests
```

## Next phase

Phase 7 implements human handover:

```text
ntheemba/workflows/
└── handover.py
```
