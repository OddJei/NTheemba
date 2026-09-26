# Phase 11.10 — Observability Operational Readiness

Phase 11.10 completes the observability workstream with fail-open health accounting, readiness integration, and a dependency-free self-check.

## Added

- `ObservabilityRuntime`
- `ManagedTraceSink`
- per-sink submitted-event and failure counters
- last failure timestamp and exception type
- observability readiness check under `GET /ready`
- protected runtime diagnostics
- synthetic nested-span self-check
- command-line validation script

## Fail-open guarantee

A trace exporter failure is recorded and swallowed by `ManagedTraceSink`. It cannot replace, mask, or interrupt the exception semantics of the customer-message workflow.

## Developer diagnostics

```text
GET  /dev/observability/runtime
POST /dev/observability/self-check
```

## Deployment self-check

From the project root:

```bash
python scripts/validate_observability.py
```

The command emits a synthetic root span and child span, validates the resulting graph, prints JSON, and exits with status `0` only when the trace is valid and complete.

## Readiness behavior

`GET /ready` now reports:

- application initialization
- whether tracing is disabled intentionally
- whether at least one sink is configured when tracing is enabled
- aggregate exporter failure count

Historical exporter failures do not make the customer service unavailable. A missing runtime or tracing enabled with zero sinks is reported as not ready.

## Completion gate

```text
283 tests passed
Ruff passed
Ruff formatting passed
MyPy strict passed
Observability self-check passed
```
