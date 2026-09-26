# Phase 2 — Ports and In-Memory Fakes

Phase 2 defines how the Ntheemba core communicates with storage, queues,
NCPC, TradeFlow, and audit infrastructure without importing those technologies.

## Added core ports

```text
ntheemba/ports/
├── __init__.py
├── sessions.py
├── publisher.py
├── audit.py
├── ncpc.py
└── tradeflow.py
```

## Added test fakes

```text
tests/fakes/
├── __init__.py
├── sessions.py
├── publisher.py
├── audit.py
├── ncpc.py
└── tradeflow.py
```

## Contract decisions

- Session saves use optimistic revision checks.
- Session locks are separate from repositories.
- Incoming-message deduplication has explicit TTL and release operations.
- Outgoing messages have ordering and idempotency keys.
- Audit events are immutable, structured, and redacted by design.
- NCPC returns canonical product identity only.
- TradeFlow returns business price, stock, visibility, services, slots, staff,
  and idempotent order/booking submission results.
- No Redis or HTTP library is imported by the ports.
- All Phase 3 application tests can use the in-memory fakes.

## Run the checks

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy ntheemba tests
```

## Next phase

Phase 3 builds:

```text
application/
├── session_coordinator.py
├── workflow_router.py
└── service.py
```

It will inject these ports and remain fully testable with the included fakes.
