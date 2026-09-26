# Phase 7 — Human Handover Workflow

Phase 7 implements controlled transfer between Ntheemba and a human operator.

## Added files

```text
ntheemba/workflows/
└── handover.py

tests/unit/workflows/
└── test_handover.py

tests/unit/application/
└── test_handover_integration.py
```

## Routed intents

`build_handover_routes()` registers:

- `HANDOVER`
- `RESUME_BOT`
- `CLOSE_SESSION`

Staff takeover is a trusted operational action exposed through
`HandoverWorkflow.activate_human(session)`. It is deliberately not inferred
from customer language.

## Customer handover flow

```text
BOT mode
    ↓ HANDOVER
Preserve order, booking, or catalogue state when configured
    ↓
HANDOVER / WAITING_FOR_HUMAN
HUMAN mode
PAUSED session
    ↓
Subsequent customer messages are recorded
    ↓
Interpreter and bot workflows are suppressed
```

## Staff takeover

```text
WAITING_FOR_HUMAN
    ↓ trusted staff action
HUMAN_ACTIVE
    ↓
Customer receives an optional staff-active notification
```

A future authenticated operations API will invoke this trusted action. It must
not be exposed as a normal customer message endpoint.

## Resume flow

When a customer workflow was preserved:

```text
HANDOVER / HUMAN_ACTIVE
    ↓ RESUME_BOT
Restore exact flow and stage
Restore pending question
Set BOT / ACTIVE
    ↓
Repeat the pending question
```

When no customer workflow was preserved, resume returns to:

```text
IDLE / START
BOT / ACTIVE
```

## Close flow

```text
WAITING_FOR_HUMAN or HUMAN_ACTIVE
    ↓ CLOSE_SESSION
IDLE / CLOSED
CLOSED session
Clear pending and suspended state
Resolve handover
```

## Safety guarantees

- Handover immediately pauses automated replies.
- Messages received during human control remain in conversation history.
- The interpreter is not called while human mode is active.
- Order, booking, and catalogue state can survive human takeover.
- Pending questions are restored exactly when bot control resumes.
- Staff takeover is a trusted operation, not an LLM/customer-language intent.
- Invalid takeover, resume, and close transitions are rejected centrally.
- Closed sessions cannot transition again.
- Audit events contain state names but not customer message contents.

## Run checks

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy ntheemba tests
```

## Next phase

Phase 8 implements NCPC-backed product resolution:

```text
ntheemba/services/
└── product_resolver.py
```
