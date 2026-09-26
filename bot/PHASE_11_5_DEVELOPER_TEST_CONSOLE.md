# Phase 11.5 — Developer Test Console

Phase 11.5 adds a browser-based console on top of the Phase 11.4 developer trace API.

## Endpoint

`GET /dev/console`

The route is registered only when `NTHEEMBA_ENVIRONMENT` is `development` or `test`.
It is absent in staging and production.

## Console capabilities

- List retained traces, newest first.
- Filter trace summaries by conversation ID.
- Inspect every event in a selected trace in chronological order.
- Display node, component, status, duration, attributes and safe error metadata.
- Refresh trace and health data without reloading the page.
- Clear the bounded in-memory trace store.
- Show retained event count, trace count and configured event limit.
- Responsive layout for desktop and narrow screens.

## Security boundaries

- No production route registration.
- No external scripts, fonts or assets.
- Content Security Policy restricts resources to the same origin.
- Framing is denied.
- Responses use `Cache-Control: no-store`.
- The console consumes the same sanitized trace DTOs as the Phase 11.4 API.

## Phase 11.4 repair carried forward

This package includes the complete application-factory wiring required by the developer API:

- one shared `InMemoryTraceSink` on `app.state.trace_sink`;
- one `TraceQueryService` on `app.state.trace_query_service`;
- developer API and console routers registered for development/test only;
- public read-only `max_events` retention property.

Replacing an incomplete local merge with this package resolves the missing `/dev/traces` route and missing `app.state.trace_sink` failures.

## Run locally

```powershell
$env:NTHEEMBA_ENVIRONMENT = "development"
python -m uvicorn ntheemba.main:app --reload
```

Open:

`http://127.0.0.1:8000/dev/console`

## Validation

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy ntheemba tests
```
