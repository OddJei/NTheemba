# Phase 11.3 — Trace Sink Adapters

Phase 11.3 gives the Phase 11.1 trace contracts and Phase 11.2 pipeline instrumentation concrete destinations.

## Added adapters

### `InMemoryTraceSink`

- retains events in emission order;
- supports single-event and batch emission;
- provides immutable snapshots;
- filters by trace ID and conversation ID;
- supports clearing for developer-console session resets;
- uses a configurable event limit and evicts the oldest records first.

It is intended for automated tests and the local Developer Test Console. It is not durable storage.

### `LoggingTraceSink`

- emits one compact JSON record per trace event;
- uses the `ntheemba.trace` logger by default;
- includes correlation IDs, timing, status, errors, and redacted attributes;
- converts enums, datetimes, mappings, and collections into JSON-safe values.

The sink does not perform redaction itself. Only already-safe trace attributes should enter the trace contract.

### `CompositeTraceSink`

- fans the same event or batch out to several sinks;
- preserves configured sink order;
- isolates adapter failures by default so observability cannot break message processing;
- optionally reports failures through an `on_error` callback;
- offers strict mode for tests and startup verification.

## Example wiring

```python
memory_sink = InMemoryTraceSink(max_events=10_000)
logging_sink = LoggingTraceSink()
trace_sink = CompositeTraceSink((memory_sink, logging_sink))
tracer = Tracer(trace_sink)
```

The same `tracer` is injected into `NtheembaService` and `WorkflowRouter`.

## Architectural outcome

The application and domain layers still depend only on the `TraceSink` port. Future Sentry and Redis adapters can join the composite without changing workflow code or the Developer Test Console.
