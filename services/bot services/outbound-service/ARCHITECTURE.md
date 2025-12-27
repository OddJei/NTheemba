# Outbound / Delivery Service — Architecture

## Purpose

Deliver channel-ready provider payloads to external messaging providers (WhatsApp, SMS gateway, HTTP callbacks). Responsible for provider adapters, rate-limiting, retries, delivery receipts, DLQ handling, and reconciliation.

## Inputs

- Stream: `outbound:requests` — payload from Reply Service. Minimal fields:
  - `event_id`, `session_id`, `provider` (wa/sms/http), `provider_payload` (channel-specific), `delivery_instructions` (priority, ttl), `callback_url` (optional), `trace_id`.
- HTTP: provider callbacks (delivery receipts) and administrative controls.

## Outputs

- Provider API calls (HTTP/SDK) to send messages.
- Stream: `outbound:receipts` — normalized delivery receipts for upstream consumption.
- Stream: `outbound:dlq` — failed sends after retry policies.

## Provider Adapters

- Implement per-provider adapter modules that:
  - Validate and map `provider_payload` to the provider's API contract.
  - Enforce provider-specific rate limits and batching.
  - Retry transient errors with backoff and jitter.
  - Normalize receipts and error codes into a common schema.

Adapter design guidelines:
- Keep adapters thin and testable. Put provider-specific transforms and auth in adapter layer only.
- Use circuit-breakers per provider to avoid cascading failures.

## Delivery Semantics & Retries

- Best-effort delivery: transient errors retried (exponential backoff), permanent errors (4xx / policy denies) move to `outbound:dlq` with diagnostics.
- Idempotency: include `event_id` as provider-level idempotency key where supported.
- Batching: for high-volume SMS providers, batch sends where supported; expose batch metrics.

## Rate Limiting & Throttling

- Global and per-provider rate limiters. Respect `delivery_instructions.priority` for ordering.
- Implement token-bucket or leaky-bucket algorithms and backpressure the consuming stream when limits are reached.

## Delivery Receipts & Reconciliation

- Normalize receipts into `outbound:receipts` with fields: `event_id`, `provider_message_id`, `status` (delivered, failed, queued), `timestamp`, `provider_error`.
- Reconciliation process: periodically reconcile provider state with `outbound:receipts` to identify missed receipts and update upstream systems.

## Failure Handling & DLQ

- Retries: configurable retry policy (default 3 attempts with backoff). On final failure write to `outbound:dlq` including original `provider_payload` and diagnostics.
- Manual replay: provide tooling to requeue DLQ entries after fix.

## Observability

- Metrics: `outbound.send.count`, `outbound.send.latency`, `outbound.retry.count`, `outbound.dlq.count`, `outbound.provider.rate_limit_events`.
- Tracing: preserve `trace_id` from ingress through to provider calls and receipts.
- Logs: structured logs with `event_id`, `session_id`, `provider`, `status`, `error_code`.

## Security & Compliance

- Store provider credentials in secure secret store; rotate credentials periodically.
- PII handling: scrub or encrypt sensitive fields before passing to providers (unless required and authorized).

## Sample flow

1. `outbound:requests` received with WhatsApp payload.
2. Select `wa` adapter, validate payload, check rate limits.
3. Call provider API with `Idempotency-Key=event_id`.
4. On success: emit `outbound:receipts` with `status=queued`/`sent`; follow provider receipts to emit `status=delivered`.
5. On repeated failure: emit `outbound:dlq` for manual review.

---

