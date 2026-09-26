# Phase 11.9 — Production Observability Bridge

Phase 11.9 connects the technology-independent tracing core to a production-safe structured-log exporter while preserving the in-memory developer sink.

## Added

- `SafeStructuredLoggingTraceSink`
- deterministic trace-level sampling
- recursive attribute redaction and value bounding
- failed-event sampling bypass
- optional running-event suppression
- error-message exclusion by default
- application-wide `app.state.tracer`
- environment-driven exporter composition

## Runtime composition

Development/test with developer tools enabled:

```text
Tracer -> Managed memory sink -> Developer API/console
       -> Managed structured-log sink -> application logs
```

Staging/production:

```text
Tracer -> Managed structured-log sink -> application logs
```

No `/dev/*` route or in-memory developer store is created in staging or production.

## Configuration

```env
NTHEEMBA_TRACING_ENABLED=true
NTHEEMBA_TRACE_EXPORT_ENABLED=true
NTHEEMBA_TRACE_SAMPLE_RATE=1.0
NTHEEMBA_TRACE_INCLUDE_RUNNING=true
NTHEEMBA_TRACE_INCLUDE_ERROR_MESSAGES=false
NTHEEMBA_TRACE_ERROR_MESSAGE_MAX_LENGTH=250
```

Sampling is deterministic from `trace_id`, so normal events from the same trace receive the same sampling decision. Failed events are always exported. Exception messages are disabled by default because they may contain customer or credential data.

The structured log schema is versioned as `ntheemba.trace.v1`.
