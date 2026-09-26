# Phase 11.4 — Developer Test API

Phase 11.4 exposes the bounded in-memory trace adapter through a developer-only FastAPI surface.

## Endpoints

- `GET /dev/traces` — list compact trace summaries.
- `GET /dev/traces/{trace_id}` — inspect every retained event for one trace.
- `GET /dev/conversations/{conversation_id}/traces` — list traces for a conversation.
- `DELETE /dev/traces` — clear retained development traces.
- `GET /dev/health/tracing` — inspect sink capacity and current counts.

The router is registered only in `development` and `test` environments. It is absent in staging and production.

## Architecture

The HTTP router does not query the adapter directly. It uses `TraceQueryService`, preserving the application boundary and making a future Redis-backed query implementation replaceable.

## Safety

Trace events remain redacted contracts. The API exposes no raw customer message body, credentials, secrets, or dependency payloads.
