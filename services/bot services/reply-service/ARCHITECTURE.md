# Reply Service — Architecture

## Purpose

The Reply Service transforms handler outcomes (from Custom/Default Bot Node Engine) into channel-ready, localized user messages. It manages templating, light NLG (LLM-assisted when needed), attachments, quick-replies/buttons, and publishes final outbound messages to the Outbound/Delivery service.

## Inputs

- Stream: `reply:requests` — canonical message request from Node Engine. Minimal structure:
  - `event_id`, `session_id`, `bot_id`, `user_id`, `channel` (wa/sms/http), `template_id` or `render_type` (`template`|`nlg`), `template_vars`, `attachments[]`, `locale`, `ttl`, `trace_id`.
- HTTP: admin updates for templates, localization files, or NLG prompt changes.

## Outputs

- Stream: `outbound:requests` — rendered channel-ready payloads for the Outbound service. Contains `provider_payload` (channel formatted), `delivery_instructions`, and fallback plain-text.
- Stream: `reply:dlq` — failed renderings after retries.

## Template & NLG Strategy

- Primary: template-based rendering using Mustache/Handlebars-like templates stored in a template store. Templates are localized and parameterized.
- Secondary: NLG (Gemini) for dynamic responses when templates are insufficient (e.g., complex summaries). Use a small deterministic NLG prompt with strict output format (JSON with `text` and optional `quick_replies`).
- Template selection:
  - If `template_id` provided → render template with `template_vars`.
  - If `render_type` == `nlg` or `template` not available → call NLG with token budget limits (prefer <=200 prompt tokens, output <=200 tokens).

## Channel Formatting

- Channel adapters normalize the rendered content into `provider_payload` per channel (WhatsApp, SMS, USSD, Web). Include fallback plain-text to use when channel features (buttons) are unsupported.
- Include `quick_replies` where supported; convert to numbered-menu for SMS.

## Personalization & Safety

- Personalize with user display name, preferred salutations and last-order context.
- Run content through safety & PII scrub filters before publish.

## Failure Handling

- Template render errors: log diagnostics, and attempt fallback to a safe default template (e.g., "Sorry, we couldn't complete that action.").
- NLG errors/timeouts: retry once; on repeated failure, fallback to template or plain-text fallback.
- Publishing errors to Outbound: retry with backoff; after N attempts, write to `reply:dlq` with full diagnostics and `provider_payload`.

## Observability

- Metrics: `reply.render.count`, `reply.nlg.calls`, `reply.render.failures`, `reply.publish.latency`, `reply.dlq.count`.
- Tracing: propagate `trace_id` from ingress through to outbound delivery. Spans: `render`, `nlg_call`, `channel_adapter`, `publish`.

## Sample request/response

Request (Node Engine -> Reply):

```json
{
  "event_id":"evt_20251226_01",
  "session_id":"sess_abc123",
  "bot_id":"bot_456",
  "user_id":"user_789",
  "channel":"wa",
  "locale":"en",
  "template_id":"confirm_add",
  "template_vars": {"product_name":"Solar Panel A","qty":2,"price":120},
  "trace_id":"trace-xyz"
}
```

Rendered Outbound (Reply -> Outbound):

```json
{
  "event_id":"evt_20251226_01",
  "session_id":"sess_abc123",
  "provider_payload": {
    "type":"text",
    "text":"Added 2 × Solar Panel A to your cart. Total: $240. Confirm checkout?",
    "quick_replies":[{"title":"Checkout","id":"checkout"},{"title":"Continue Shopping","id":"browse_more"}]
  },
  "delivery_instructions": {"channel":"wa","priority":"normal"}
}
```

## NLG (Gemini) specifics

- For NLG use, enforce token budgets: prefer prompt <=200 tokens and output <=200 tokens. Temperature: 0.0-0.2. Use system message to require JSON-only outputs when NLG returns structured objects.

## Templates & Versioning

- Templates should include `template_version` metadata. When migrating templates, keep rolling updates and allow fallback to prior versions for a grace period.

## Testing

- Unit tests for templates (render with sample `template_vars`).
- Integration tests that run through the channel adapter to ensure `provider_payload` compatibility.

---

