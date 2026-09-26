# Phase 3 — Application Orchestration

Phase 3 implements the complete infrastructure-independent message pipeline.

## Added application modules

```text
ntheemba/application/
├── __init__.py
├── session_coordinator.py
├── workflow_router.py
└── service.py
```

## SessionCoordinator

- acquires a per-business/customer session lock;
- loads or creates a session;
- archives and replaces expired or closed sessions;
- exposes explicit commit and rollback operations;
- refreshes activity and expiry during commit;
- uses optimistic repository revisions;
- keeps recent conversation history bounded.

## WorkflowRouter

- receives a typed intent proposal;
- authorizes it through TransitionPolicy;
- dispatches only to a registered handler;
- returns structured replies and audit events;
- performs no external publication itself.

## NtheembaService

The processing order is:

```text
claim message ID
→ audit acceptance
→ lock/load session
→ record customer turn
→ suppress bot when human mode is active
→ interpret message
→ authorize and route workflow
→ rollback partial mutation on workflow failure
→ commit session atomically
→ publish ordered idempotent replies
→ audit completion
```

## Safety decisions

- Duplicate messages never reach interpretation or workflows.
- Workflow mutation is rolled back before a fallback response is saved.
- Human mode records messages but suppresses automated replies.
- Audit storage is best effort and cannot block a customer reply.
- Infrastructure failures release the deduplication claim for a later retry.
- Outgoing replies carry conversation ordering and idempotency keys.
- FastAPI, Redis, NCPC HTTP, TradeFlow HTTP, and LLM SDKs remain outside this layer.

## Tests

Phase 3 includes tests for:

- session creation, commit, rollback, expiry, and archive;
- valid and invalid workflow routing;
- unregistered workflows;
- complete processing and publication;
- duplicate suppression;
- human-mode suppression;
- workflow failure rollback;
- audit failure tolerance.

## Next phase

Phase 4 builds interpretation and validation:

```text
services/
├── interpretation.py
└── validation.py
```
