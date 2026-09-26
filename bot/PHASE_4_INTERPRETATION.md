# Phase 4 — Interpretation and Validation

Phase 4 adds a deterministic, testable interpretation service and a strict
validation boundary for any model-proposed intent.

## Added files

```text
ntheemba/services/
├── __init__.py
├── interpretation.py
└── validation.py
```

## Interpretation order

```text
1. Global commands
2. Strong pending-question answers
3. Safe side-question interruption
4. Clear new requests
5. Validated model fallback
6. Typed clarification fallback
```

A pending selection is only accepted when it strongly matches a number, a
size such as `500g`, or one of the options saved with the pending question.
This prevents `What time do you close?` from being mistaken for a product
selection.

## Model safety

The model cannot directly assert TradeFlow or NCPC facts such as:

- price;
- stock;
- availability;
- business product IDs;
- NCPC product IDs;
- service or slot IDs;
- order or booking request IDs.

Model output is converted into domain enums and `EntitySet`. Unsupported
fields or malformed values are rejected. Low-confidence output becomes a
`CLARIFY` intent instead of being executed.

## Test command

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy ntheemba tests
```

## Next phase

Phase 5 creates `services/response_builder.py`, centralizing concise,
customer-safe replies for workflows.
