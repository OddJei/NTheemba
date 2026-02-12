# Reply Service — Implementation Guide

This guide explains how the Reply Service works and how to set it up. It's written simply so a high-school student can understand.

What the Reply Service does

- Takes a user's message and some context (cart, last messages).
- Takes a user's message and some context (cart, last messages).
- Asks a language model (Gemini) to write a friendly reply in the voice of the business for that session (use `{business_name}`) while the assistant introduces itself by its stable persona (NTheemba) — the assistant persona defaults to `NTheemba` and is shown to users (e.g., "NTheemba at Agrep: ...").
- Ensures replies are polite, warm, and include a little local language (about 10% Nyanja/Bemba phrases).
- Returns the reply to the bot runtime, and records telemetry and audit events. Internal logs/metrics may reference the product/agent name `NTheemba` for tracing.

Main components

- API endpoint: receives a message and context, returns a reply.
- Intent helper (optional): suggests which model/settings to use and extracts intent/slots.
- Gemini client wrapper: talks to the Gemini model safely (handles errors, retries, and budget limits).
- Prompt templates: pre-defined messages that tell Gemini how to speak and behave.
- Safety/filters: checks model output for disallowed content and sensitive data.
- Telemetry & audit: logs traces, token usage, and important events for observability.

Basic flow (step-by-step)

1. Bot sends a request to Reply Service with: session info, last messages, cart summary.
2. Reply Service asks the Intent Helper (if available) what model and settings to use.
3. Reply Service builds a prompt using templates and the session context.
4. The Gemini client sends the prompt to the Gemini API and gets a generated reply.
5. Reply Service runs safety and PII checks, adjusts wording if needed.
6. Reply Service returns the final text to the bot and emits telemetry.

- Tone: warm, polite, helpful, and business-like (it sounds like the shop).
- Local flavor: include one short Nyanja/Bemba phrase roughly once every 8–10 sentences (about 10% of text). Keep the main sentence in English.
- Use local phrases for greetings, thanks, or small friendly notes only (do not use in legal/price text).
- Examples:
  - "Added Cool Product to your cart. Cart now has 1 item(s). Reply 'REVIEW ORDER' to continue or 'ADD MORE' to add more. Zikomo!"
  - "Order ready. 1 item(s). Total: 199. Reply 'CONFIRM ORDER' to place the order. Twalumba — we appreciate your business."

Assistant persona vs business name

- The assistant has a stable persona name (NTheemba) that is visible to users and does not change across deployments. The assistant speaks on behalf of the per-session `{business_name}`. Example: "NTheemba at Agrep: Added Cool Product to your cart..."
- Use `product:NTheemba` in telemetry and logs to identify the product/service, but render per-session prompts with NTheemba and `{business_name}` only.
- Tone: warm, polite, helpful, and business-like (it sounds like the shop).
- Local flavor: include one short Nyanja/Bemba phrase roughly once every 8–10 sentences (about 10% of text). Keep the main sentence in English.
- Use local phrases for greetings, thanks, or small friendly notes only (do not use in legal/price text).
- Examples:
  - "Added Cool Product to your cart. Cart now has 1 item(s). Reply 'REVIEW ORDER' to continue or 'ADD MORE' to add more. Zikomo!"
  - "Order ready. 1 item(s). Total: 199. Reply 'CONFIRM ORDER' to place the order. Twalumba — we appreciate your business."

Keys, environments, and safety

- Development keys: store dev-only model keys in a local `.env` or a dev secret store. Mark them clearly as non-production.
- Production keys: never store in code. Use a real secrets manager and rotate keys regularly.
- PII handling: remove or mask phone numbers, payment tokens, or other personal info before sending to Gemini unless absolutely needed.
- Safety: always run model output through a safety filter. If the reply fails the filter, replace it with a safe template.

Testing and local development

- Mock the Gemini client to return canned replies for unit tests.
- Test the prompt templates and the frequency of local-language inserts.
- Add integration tests that simulate common flows: affiliate token → add to cart → review → confirm.

Cost and scaling tips

- Use smaller models for short transactional replies; reserve larger models for complex conversations.
- Limit tokens per request and monitor token usage to avoid surprises.
- Cache static replies and reuse templates where possible.

Observability and operations

- Emit trace ids and spans for each request.
- Record token usage, latency, and errors to metrics.
- Alert on token-cost spikes and high error rates.

Next steps (recommended)

1. Draft the system prompt and a small set of example prompts for the main flows (use `{business_name}` placeholder and render per-session).
2. Implement the Gemini client with a dev/mock mode and strict retry/circuit-breaker rules.
3. Create a small phrase bank of vetted Nyanja/Bemba phrases and have a native speaker review them.
4. Add tests for safety, localization frequency, and cost controls.

Implementation checklist

- [ ] Draft and vet the system prompt using NTheemba and `{business_name}` placeholders (see `REPLY_SYSTEM_PROMPT.md`). Render it per-session before sending to the model.
- [ ] Ensure user-facing text shows NTheemba.
- [ ] Implement Gemini client wrapper with dev/mock mode, retries, and circuit breaker.
- [ ] Add secrets management integration (dev keys in `.env`, prod keys in secrets manager).
- [ ] Build prompt template library for transactional flows (token, review, confirm, payment).
- [ ] Create and review Nyanja/Bemba phrase bank with native speakers.
- [ ] Add unit tests for prompt templating and mock Gemini responses.
- [ ] Add integration E2E tests: token → add to cart → review → confirm → payment webhook.
- [ ] Add telemetry and cost metrics (tokens, latency, errors); set alerts.
- [ ] Create deployment pipeline with staging and canary steps.
- [ ] Run localization QA and safety/red-team tests before production rollout.

The drafted system prompt is stored next to this file as `REPLY_SYSTEM_PROMPT.md`.

If you'd like, I can now draft the actual system prompt for `NTheemba` and a starter Gemini client wrapper (dev-mode + retries). Which should I do next?
