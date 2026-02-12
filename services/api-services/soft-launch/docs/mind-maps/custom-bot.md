**Custom Bot — Focused Mind Map**

- **Responsibility**: Consume enriched payloads from `bot:lane:{bot_type}`, build execution context, orchestrate multi‑intent execution (chat → cart → order → payment → delivery), and emit outbound intents for delivery.

- **Inputs**:
  - Enriched payloads from ICE (must include `hydration` blobs: session, business, user, affiliate, cart/order snapshot).
  - `need_intent` flag to toggle strict intent mapping vs direct execution.

- **Core behavior**:
  - Validate idempotence for incoming enriched messages (use `request_id` / `event_id`).
  - Build context using OOB snapshots first, then call ICE for authoritative data when cache missing/stale.
  - Use a multi‑intent executor with canonical stage order: `chat → cart → order → payment → delivery`.
  - For each stage, perform the minimal authoritative operation via ICE (e.g., cart updates, call `POST /reserve`, call `POST /confirm`).

- **LLM / response generation**:
  - Construct LLM prompts with sanitized context (no raw secrets), validate LLM output, and map responses to executor actions.
  - Fallbacks: simple templates when LLM is unavailable.

- **Outbound message flow**:
  - When bot sends a message to user, publish an `outbound:request` containing only `to`, `from`, `reply_text`, `meta.platform`, `bot_id` after recording any state change via ICE.
  - Do NOT write authoritative outbound persistence locally; call ICE endpoint to persist outbound (ICE will write Outbox/DB records as authoritative).

- **Error handling & retries**:
  - Retry transient ICE calls with bounded retries; surface deterministic failures to the user when appropriate.
  - Log and emit `bot.action.failed` events to audit via Outbox when actions affecting money/attribution fail.

- **Observability**:
  - Metrics: `bot.requests`, `bot.intent_executions`, `bot.stage_latency`.
  - Include `X-Correlation-Id` on all calls.

- **Security & privacy**:
  - Avoid logging full PII in LLM prompts; mask phone numbers and keys.

-- End
**Custom Bot Service — Focused Mind Map**

- **Responsibility**: Consume enriched payloads from `bot:lane:{bot_type}`, build execution context, call LLM (Gemini), run multi-intent executor (chat → cart → order → payment → delivery), publish outbound requests.

- **Key endpoints / topics**:
  - Consume: `bot:lane:{bot_type}`
  - Publish outbound: `outbound:request`
  - Session updates: `ice:session:update`

- **LLM policy**:
  - Primary: Gemini.
  - Timeout: 5s; retry once; if still invalid/timeouts, fallback to deterministic template.
  - Strict schema validation: responses must validate against service schema; on failure retry once then fallback to template.

- **Context building**:
  - Read from OOB first (cache‑first) for product, cart, session snapshots.
  - If missing or stale, call ICE authoritative endpoints.

- **Executor**:
  - Canonical order: chat → cart → order → payment → delivery.
  - Each stage is idempotent and reports status to ICE.
  - For affiliate cycles, `intent` is OFF and executor maps to cart intent.

- **Example execution payload (to Gemini)**

```json
{
  "session": { "session_id":"sess-456","cycle_id":"cycle-999" },
  "context": { "cart": {"items":[]}, "product_snapshot":{}}
}
```

- **Mermaid flow**:

```mermaid
flowchart TD
  A[bot:lane] --> B[Build Context (OOB)]
  B --> C[Call Gemini (5s timeout)]
  C --> D[Validate Schema]
  D -->|valid| E[Executor Run]
  D -->|invalid| F[Retry -> Gemini]
  F -->|still invalid| G[Fallback Template]
  E --> H[Publish outbound if needed]
```

- **Operational notes**:
  - Track LLM latency/failure rates; separate metrics for retries and fallbacks.
  - Keep deterministic templates for critical flows (payments, OTPs, confirmations).
