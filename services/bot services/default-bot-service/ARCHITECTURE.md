# Default Bot Service — Architecture

## Purpose

The Default Bot Service provides a low-latency, rules/menu-driven bot for merchants that do not require a full custom Node Engine. It consumes canonical enriched envelopes from `bot:lane:default`, performs lightweight state transitions (menu navigation, basic cart actions), and emits `reply:requests` for user-facing responses.

## Inputs

- Stream: `bot:lane:default` — canonical enriched envelopes published by Ingress.
- Optional: `intent:results` — intent outcomes when the flow requires intent resolution (only for a small subset of ambiguous steps).
- Optional: ICE HTTP endpoints (hydrate/reserve/confirm) for authoritative operations.

## Outputs

- Stream: `reply:requests` — canonical reply requests for the Reply Service.
- Stream: `default-bot:dlq` — failed envelopes after retries.
- Optional: `oob:audit` — append-only audit events for state changes (when enabled).

## State Model (Redis)

- `cache:session:{session_id}` — current menu node and flags (`current_node`, `expected_input`, `intent_required`, `hydrated_at`, `schema_version`).
- `cache:order_draft:{session_id}` — lightweight cart/order draft when the default bot supports cart flows.

The Default Bot must follow optimistic updates for `cache:order_draft` (via `cart_version`) and rehydrate from ICE on conflicts.

## Flows

- Menu navigation: determine the next menu node based on `current_node` + user input; publish a `reply:requests` with `template_id` and `template_vars`.
- Basic cart: add/remove/update quantities in `cache:order_draft:{session_id}` and publish confirmation replies.
- Checkout handoff: when transitioning to checkout, request ICE reservation (`POST /api/v1/reserve`) and store `reservation_id` on the draft; on success publish a checkout reply; on failure route to a correction reply.

## ICE Interactions

- Hydration (sync): on cache-miss or stale session/order_draft, call `POST /api/v1/hydrate/session`.
- Reservation: call `POST /api/v1/reserve` before final checkout confirmation.
- Confirmation: call `POST /api/v1/confirm_order` only when payment is verified/accepted.

All calls must include `event_id` / `Idempotency-Key` for stable retries.

## Failure Handling

- Retries: transient errors (Redis/ICE/network) retry with backoff (default 3 attempts).
- Idempotency: use `idempotency:request:{event_id}` to dedupe.
- Degraded mode: if ICE is unavailable and cache exists, proceed with `stale=true` for non-critical steps; never complete checkout without ICE confirmation.
- DLQ: publish to `default-bot:dlq` with diagnostics, original envelope, and any partial state.

## Observability

- Metrics: `defaultbot.requests`, `defaultbot.node.latency`, `defaultbot.ice.calls`, `defaultbot.dlq.count`, `defaultbot.stale_fallback.count`.
- Tracing: propagate `trace_id` from ingress; spans for `state_load`, `state_update`, `reply_publish`, `ice_call`.
- Logs: structured logs with `event_id`, `session_id`, `bot_id`, `current_node`, `action_status`.
