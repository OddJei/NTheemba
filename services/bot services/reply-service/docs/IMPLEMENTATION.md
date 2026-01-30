# Reply Service — Implementation (NTheemba)

This document is the implementation checklist + contracts for the Reply Service in the message flow:

Ingress → Intent (Gemini) → Custom Bot (Node Engine) → Reply (Gemini-assisted) → Outbound

## Identity rules

- **Assistant persona name:** `NTheemba` (stable, user-visible).
- **Business name:** per-session `{business_name}` (the shop/merchant the user is interacting with).
- Replies should sound like: **"NTheemba at {business_name}: …"** (configurable; see env vars).

## What Reply Service does

Consumes `reply:requests` and publishes `outbound:requests`.

Responsibilities:

- Convert bot outcomes (template/text + context) into a final user message.
- Optionally call Gemini to polish language and add light local flavor.
- Enforce safety/PII rules (no leaking phone numbers/payment tokens).
- Format payloads per channel/platform for Outbound.

Non-goals (for Phase 1):

- No full template store / CMS.
- No buttons/quick replies unless already provided.

---

## Redis stream contracts

### Input stream: `reply:requests`

Reply must accept both of these shapes:

1. **Current Custom Bot output** (produced by `custom-bot-service/app/publish.py`):


- Redis stream fields: `event_id`, `session_id`, `next_node`, `payload` (JSON string), optional `trace_id`, `span_id`.
- `payload` JSON typically contains: `text`, `next_node`, `meta`.

1. **Future canonical reply request** (as per Reply architecture):


- `event_id`, `session_id`, `bot_id?`, `user_id?`, `channel?`, `render_type?`, `template_id?`, `template_vars?`, `meta?`, `trace_id?`.

### Output stream: `outbound:requests`

Outbound expects a stream entry with a JSON string under the `payload` field.

Example:

```json
{
  "payload": "{\"event_id\":\"evt_...\",\"session_id\":\"sess_...\",\"meta\":{\"platform\":\"http\"},\"provider_payload\":{\"type\":\"text\",\"text\":\"...\"},\"delivery_instructions\":{}}"
}
```

---

## Gemini usage (Reply NLG)

Reply can optionally call Gemini to produce the final text.

Guidelines:

- Prefer deterministic templates when possible.
- If using Gemini, require **JSON-only** output:

```json
{"text":"..."}
```

- Include the persona (`NTheemba`) + `{business_name}` in the system instruction.

### Payment method collection rule

If the user is selecting payment, **collect only the mobile number**. The backend resolves the provider (MTN/Airtel/etc). Reply prompts and templates must not ask for "choose MTN vs Airtel".

---

## Phase 1 implementation checklist (do these in order)

### A) Worker + API skeleton

- [ ] FastAPI app with `/healthz` (+ optional `/metrics`).
- [ ] Background worker consuming `reply:requests` with a consumer group.
- [ ] DLQ stream `reply:dlq` for unrecoverable render errors.

### B) Request parsing + compatibility

- [ ] Accept `payload`-wrapped requests (custom-bot) and canonical requests.
- [ ] Normalize into one internal `ReplyRequest` model.

### C) Rendering

- [ ] Default render: `final_text = prefix(persona, business_name) + base_text`.
- [ ] Optional Gemini polish step controlled by env flags.
- [ ] Ensure safe fallback reply on any failure.

### D) Publish to Outbound

- [ ] Convert to Outbound contract (`outbound-service/app/models.py::OutboundRequest`).
- [ ] Write to `outbound:requests` as `{ "payload": json.dumps(outbound_request_dict) }`.

### E) Observability

- [ ] Structured logs include `event_id`, `session_id`, `trace_id`.
- [ ] Basic counters: rendered, published, failed, dlq.

### F) Tests

- [ ] Unit test: custom-bot `payload` shape → outbound payload.
- [ ] Unit test: prefix formatting (NTheemba + business name).

---

## Environment variables (Reply Service)

- `REDIS_URL` (default `redis://localhost:6379/0`)
- `REPLY_REQUESTS_STREAM` (default `reply:requests`)
- `REPLY_DLQ_STREAM` (default `reply:dlq`)
- `OUTBOUND_REQUESTS_STREAM` (default `outbound:requests`)
- `REPLY_CONSUMER_GROUP` (default `reply-workers`)
- `REPLY_CONSUMER_NAME` (default `reply-service`)

Identity:

- `REPLY_PERSONA_NAME` (default `NTheemba`)
- `REPLY_BUSINESS_NAME_DEFAULT` (default `your business`)
- `REPLY_PREFIX_STYLE` (default `persona_at_business`) values: `persona_at_business|persona_only|none`

Gemini:

- `REPLY_GEMINI_ENABLED` (default auto: True if key present)
- `REPLY_GEMINI_API_KEY`
- `REPLY_GEMINI_MODEL` (default `gemini-1.5-pro`)
- `REPLY_GEMINI_ENDPOINT` (default `https://generativelanguage.googleapis.com/v1beta/models`)
- `REPLY_GEMINI_MAX_OUTPUT_TOKENS` (default `120`)

---

## Local run (Phase 1)

```powershell
Set-Location "c:\Users\SMART PC\Documents\NTheemba\services\bot services\reply-service"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$Env:REDIS_URL = "redis://localhost:6379/0"
uvicorn app.main:app --reload --port 8013
```
