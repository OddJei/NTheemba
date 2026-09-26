# Phase 11.1 — Observability Foundation

Phase 11.1 adds technology-independent execution tracing without changing any
workflow behaviour.

## Delivered

- Immutable `TraceEvent` lifecycle contracts.
- `TraceStatus`: running, passed, failed and skipped.
- Correlated `TraceContext` propagation using `contextvars`.
- Root and child span creation.
- Technology-independent `TraceSink` port.
- Reusable async `Tracer.span(...)` lifecycle manager.
- No-op trace sink for deployments where tracing is disabled.
- `@trace_node(...)` decorator for async application methods.
- Exception preservation: failures are emitted and the original exception is re-raised.
- Unit coverage for validation, context restoration, nesting, success, failure and decoration.

## Security boundary

Trace attributes are deliberately explicit. Application instrumentation must not add
passwords, access tokens, complete customer messages, phone numbers, addresses, or
other secrets. Redaction policy and concrete sinks are added in later side-integration
phases.

## Next

Phase 11.2 instruments meaningful execution boundaries in `NtheembaService`, session
coordination, interpretation, workflow routing, external dependency calls, session
commit and reply publication.
