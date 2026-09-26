# Phase 1 — Domain Foundation

Phase 1 introduces the pure Ntheemba domain model.

## Added modules

```text
ntheemba/domain/
├── __init__.py
├── enums.py
├── intents.py
├── order_draft.py
├── booking_draft.py
├── product_resolution.py
├── session.py
└── transitions.py
```

## Domain guarantees

- No FastAPI, Redis, HTTP, queue, NCPC SDK, TradeFlow SDK, or LLM imports.
- Intent interpretation is represented as a proposal, not an authorized action.
- `TransitionPolicy` is the central source of permitted actions and state changes.
- Orders and bookings use typed drafts rather than arbitrary dictionaries.
- Final submission requires external validation state.
- Product resolution keeps canonical NCPC identity separate from business facts.
- Relative size can compare recognized units such as grams and kilograms.
- Sessions support bounded history, clarification limits, interruption, resume, cancellation, handover, closure, and expiry.

## Run Phase 1 checks

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy ntheemba tests
```

## Next phase

Phase 2 defines external ports and in-memory fakes for sessions, locking, deduplication, publishing, audit, NCPC, and TradeFlow.
