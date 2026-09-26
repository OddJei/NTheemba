# Phase 11.8 — Observability Validation and Completion

Phase 11.8 closes the trace-model implementation by validating retained traces as coherent execution graphs instead of treating them as unrelated log records.

## Added

- `ntheemba/observability/validation.py`
- per-trace and whole-snapshot validation in `TraceQueryService`
- developer validation endpoints
- unit and HTTP coverage for valid, incomplete, and corrupt traces

## Validation rules

Each trace is checked for:

- one trace ID across the report
- unique event IDs
- one running event per span
- no more than one terminal event per span
- terminal events occurring after their running event
- stable node, component, and parent metadata inside a span
- existing parent spans
- exactly one root span
- consistent request, business, conversation, and message correlation IDs

A trace can be **valid but incomplete** while a span is still running. Missing terminal events are warnings; structural contradictions are errors.

## Developer endpoints

```text
GET /dev/observability/validation
GET /dev/traces/{trace_id}/validation
```

The endpoints remain protected by the Phase 11.7 developer-tooling security middleware and are excluded from OpenAPI.
