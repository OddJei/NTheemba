# Phase 11.2 — Pipeline Instrumentation

Phase 11.2 connects the Phase 11.1 tracing contracts to the real Ntheemba message-processing path. Tracing remains optional and uses the no-op sink by default, so existing deployments and tests do not need an observability backend.

## Traced boundaries

Each message now creates one root `message.process` span and nested spans for:

1. `message.deduplicate`
2. `session.open`
3. `message.interpret`
4. `workflow.route`
5. `transition.validate`
6. `workflow.execute`
7. `session.commit`
8. `reply.publish`
9. `message.release_claim` when infrastructure recovery is required

The router receives the same `Tracer` instance as the service so transition and workflow spans remain children of the routing span.

## Failure semantics

Tracing never swallows application exceptions. A failing boundary emits `FAILED` and re-raises the original exception. Existing Ntheemba recovery behavior then continues normally:

- workflow failures roll back the session and publish a safe fallback;
- publisher or session infrastructure failures release the deduplication claim;
- duplicate messages stop after deduplication;
- human-mode messages commit without interpretation or workflow execution.

## Data safety

Only operational metadata is attached to spans. Raw message text is not included. The root span records message length and customer correlation identifiers, while workflow spans record the normalized intent type.

## Completion gate

- Existing 201 tests remain green.
- New pipeline tracing tests verify ordering, nesting, failures, retries, and duplicates.
- Ruff, formatting, and strict MyPy pass.
