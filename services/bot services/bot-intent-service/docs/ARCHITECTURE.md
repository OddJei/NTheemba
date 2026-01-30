# Bot Intent Service — Architecture

## Purpose

The Bot Intent Service resolves intent classification and slot extraction when bot handlers require it (typically when `intent_required=true` on the session/envelope). It returns a compact intent result (intent id, confidence, extracted slots) and a decision whether the message requires a downstream `reply` or `outbound` action.

## Inputs

- Stream: `intent:requests` — intent resolution requests emitted by bot services (Custom/Default Bot). Minimal fields:
  - `event_id`, `session_id`, `bot_id`, `bot_type`, `raw_text`, `enriched_meta` (current_node, small order_summary refs), `trace_id`.
- HTTP: admin prompts to reload prompt templates or update model configs.

## Outputs

- Stream: `intent:results` — message per processed envelope with structure:
  - `event_id`, `session_id`, `intent`: `{ id, name, confidence }`, `slots`: `{ key: value }`, `intent_required` (bool), `next_action` (`reply`|`outbound`|`none`), `diagnostics` (optional), `raw_input`.
- Stream: `intent:dlq` — failed processing after retries.

Notes:

- Bots should correlate `intent:results` back to the originating `event_id`.

## Prompt/Model Strategy

Design goals:

- Prefer small, specialized models for intent classification (low latency) and use LLMs for complex slot parsing only when necessary.
- Use a two-stage approach: 1) Fast classifier (scikit-learn/LightGBM/onnx or small model) for intent id + confidence. 2) If confidence < threshold or slot parsing needed, call a richer LLM slot-extractor with a structured prompt.

Context assembly:

- Always include `session_context.current_node`, `order_draft` summary (max N items), `bot_meta.supported_payment_methods` and recent `user` preferences.
- Limit tokens by summarizing large blobs (catalog snapshots) into short lists or references (e.g., `catalog_snapshot_id`).

Prompt template (slot extraction example):

System: "You are a slot extraction assistant. Return JSON with keys 'intent','slots'. Use the given context and do not fabricate unknown values."

User prompt (shortened):
"Context: {session.current_node}, {order_summary} \nUser: {raw_text} \nReturn: JSON"

Model fallback:

- If model returns malformed JSON or low confidence, run a small deterministic extractor (regex/keyword) and mark `diagnostics.fallback="deterministic"`.

## Safety & Guardrails

- Content filtering: run an inline filter for PII, offensive content, and blocked actions. If unsafe, mark `intent: id = 'blocked'` and route to `intent:dlq` or human review flow.
- Token limits: cap prompt+context to configured token budget (e.g., 1500 tokens). Trim `order_draft` and `catalog_snapshot` fields first.
- Rate limiting: per-bot and per-user QPS limits to protect model costs.
- Determinism: store model `model_id` and `prompt_version` in `diagnostics` for reproducibility.
- Safety retry: do not retry more than once on explicit policy denials; escalate to human review if repeated.

## Failure Handling

- Retries: transient model/service errors — retry once with backoff, then push to `intent:dlq`.
- Fallbacks: on low-confidence results, fall back to deterministic rules (keywords, regex) and set `diagnostics.fallback="deterministic"`.
- Circuit breaker: if model error rate exceeds threshold, enter degraded mode and route all intents through deterministic classifier until recovery.
- Idempotency: use `idempotency:request:{event_id}` to detect duplicate processing; return previous intent result when present.
- Audit: every DLQ entry must include original envelope, model inputs, and raw model output for debugging.

## Observability

- Emit these metrics, traces, and logs:

- Metrics:
  - `intent.requests` (counter) by `bot_id`, `model_id`
  - `intent.latency` (histogram) model per-call latency
  - `intent.confidence` (histogram) distribution
  - `intent.fallback.count` (counter) when deterministic fallback used
  - `intent.dlq.count`

- Tracing: propagate `trace_id` from ingress; create spans for `classify`, `slot_extract`, and `model_call`.
- Structured logs: record `event_id`, `session_id`, `bot_id`, `intent_id`, `confidence`, `model_id`, `prompt_version`, and `diagnostics`.

---

## Integration & Runtime Contract

- Source: `intent:requests` (bots request intent only when needed).
- Primary publish: `intent:results` (intent outcomes). For synchronous flows, support HTTP `POST /v1/intent/resolve` returning JSON result.
- Idempotency: all requests carry `event_id` and `Idempotency-Key` to dedupe.

## Intent RPC / Queue Contract (examples)

- Queue message (from bot consumer -> intent service):

```json
{
 "event_id":"evt_20251226_01",
 "session_id":"sess_abc123",
 "bot_id":"bot_456",
 "raw_text":"I want to buy 2 Solar Panel A",
 "enriched_meta": { "current_node":"serve_products", "order_draft_ref":"cache:order_draft:sess_abc123" }
}
```

- Intent result (published by intent service):

```json
{
 "event_id":"evt_20251226_01",
 "session_id":"sess_abc123",
 "intent": {"id":"add_item","name":"Add Item","confidence":0.93},
 "slots": {"product_id":"p_123","quantity":2},
 "next_node":"serve_products",
 "diagnostics": {"model_id":"intent-v1","latency_ms":120}
}
```

## Prompt Templates & Fallback Strategy

- Fast stage (classifier): small model returns `intent_id` + `confidence`. If `confidence >= 0.80`, accept and return quickly.
- Second stage (slot extraction): if `confidence < 0.80` or `slots` required, call LLM slot-extractor with this template:

System:
"You are a slot extraction assistant. Return strict JSON with keys `intent` and `slots`. Use context, do not hallucinate."

User (context):
"Context: node={current_node}; order_summary={order_summary}; User: {raw_text}"

- If LLM returns malformed JSON, run deterministic fallback (regex/keyword) and tag `diagnostics.fallback`.

## Model Config & Thresholds

- `classifier_confidence_accept`: 0.80 (configurable)
- `slot_extraction_timeout_ms`: 1500
- `llm_retries`: 1 (on transient errors)

### LLM (Gemini) usage & token budget

We recommend using a Gemini-family model for slot extraction / complex intent disambiguation with strict token budgets to control latency and cost.

- **Token budget policy (hard limits):**
  - Preferred prompt tokens (context + user): <= 200 tokens.
  - Allowed maximum total tokens (prompt + model output): <= 500 tokens.
  - Enforce at call-time: if prompt tokens > 200, trim context (order_summary, catalog_snapshot) or summarize; if trimmed prompt still exceeds allowed max, fall back to deterministic extractor and emit `diagnostics.fallback="trimmed_context"`.

- **Model parameters (recommended):**
  - `model`: `gemini-1.5` (or configured variant)
  - `temperature`: 0.0 - 0.2 (deterministic)
  - `max_output_tokens`: 128 (ensure prompt + output <= 500)
  - `stop` sequences: ensure JSON closure to limit extraneous text

- **Prompt assembly rules:**

 1. Start with minimal system instruction explaining strict JSON output and do-not-hallucinate rule.
 2. Include `current_node` and a maximum `order_summary` of N items (truncate to keep prompt <=200 tokens).
 3. Include the `raw_text` user utterance.
 4. If additional context is needed (catalog snapshot), replace full lists with `catalog_snapshot_id` and pass a separate `catalog_summary` of at most M items.

- **Token measurement & enforcement:**
  - Measure tokens using the same tokenizer as the Gemini family. Compute `prompt_tokens + max_output_tokens <= 500` before sending.
  - If measurement would exceed limits, apply trimming order: `catalog_snapshot` -> `order_summary` -> `recent_history`.

- **Failure/Timeout handling:**
  - Timeout for LLM call: `slot_extraction_timeout_ms` (default 1500ms). On timeout or transient 5xx, retry once. On repeated failures, run deterministic fallback and mark `diagnostics.fallback="llm_unavailable"`.

- **Observability metrics to add:**
  - `intent.gemini.calls` (counter)
  - `intent.gemini.tokens.consumed` (counter)
  - `intent.gemini.over_limit` (counter) when prompt exceeded budget and was trimmed/fallback used
  - `intent.gemini.latency` (histogram)

Example Gemini request (pseudo-HTTP):

```http
POST /v1/models/gemini-1.5:generate
Content-Type: application/json

{
 "prompt": {
  "system": "You are a strict JSON slot extractor. Return only valid JSON with keys 'intent' and 'slots'. Do not hallucinate.",
  "user": "Context: node=serve_products; order_summary=...; User: I want 2 Solar Panel A"
 },
 "max_output_tokens": 128,
 "temperature": 0.0
}
```

Notes: enforce token accounting client-side before issuing the request. Prefer deterministic low-temperature settings for production intent extraction.

## Testing & Validation

- Unit: classifier mapping table and slot-extraction prompt tests.
- Integration: end-to-end test from `bot:lane` -> intent service -> `intent:results` -> custom-bot handler.
- Regression: add samples for low-confidence and ambiguous inputs to prevent drift.

## Observability Additions (Intent)

- Add `intent.request.count`, `intent.model.latency`, `intent.confidence.distribution`, `intent.fallback.count`, and `intent.dlq.count`.
- Trace spans: `intent.resolve` (classifier), `intent.slot_extract` (LLM), and propagate `trace_id`.

---
