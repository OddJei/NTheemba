# Intent Context Spec for Gemini LLM — Custom Bot Service

Purpose

- Provide a concise, machine-checkable contract between the runtime and the Gemini intent extractor.
- Ensure the LLM returns predictable JSON using canonical intent ids the runtime expects.

Summary (what the LLM must return)

- A single JSON object with keys: `event_id`, `session_id`, `intents` (ordered non-empty list), `next_action` (one of `reply|outbound|none`), and optional `suggested_next_node`, `diagnostics`.
- Each item in `intents` MUST be an object with keys: `id` (one of canonical ids), `confidence` (0..1), `slots` (map). `hints` is optional.

Source-of-truth

- See `docs/custom_bot_gemini_context.md` for per-intent slot schemas and service-specific mapping. The canonical ids listed there are authoritative.

Required JSON schema (strict)

```json
{
  "event_id": "string",
  "session_id": "string",
  "intents": [
    {
      "id": "string",              
      "confidence": 0.0,            
      "slots": {"slot_name": null},
      "hints": {                    
        "required_blobs": ["string"],
        "force_authoritative": false
      }
    }
  ],
  "next_action": "reply|outbound|none",
  "suggested_next_node": "string|null",
  "diagnostics": {"nlp_latency_ms": 0}
}
```

LLM system prompt (recommended template)

Use a strict instruction that enumerates canonical ids and requires JSON-only output. Example single-line system instruction:

"You are an intent+slot extraction service for the Custom Shopping Bot. RETURN ONLY ONE JSON OBJECT with NO MARKDOWN and NO extra text. The object MUST contain `intents` (non-empty array) and `next_action`. Each detected intent object MUST use `id` equal to one of the canonical ids listed in the Appendix. If no canonical id applies, set `id` to `unknown`. Do NOT invent new intent ids or synonyms. Confidence must be a float between 0 and 1. Slots must be JSON primitives or objects; when unsure use null."

Canonical intent ids (short)

- add_item
- unknown
- view_cart
- confirm_order
- confirm_payment
- cancel
- help
- clear_cart
- remove_item
- track_order
- request_support

(Full per-service intent list and slot schemas: `docs/custom_bot_gemini_context.md`)

Slot naming & normalization rules

- `product_id` preferred over `product_name` when exact id available.
- `quantity`: integer.
- `fulfillment_type`: `delivery` | `pickup` | null.
- `address`: object with `street`, `city`, `zone` when available; use `address_ref` for stored address ids.
- `payment_method`: `mtn` | `airtel` | `card` | `cash` | null.
- `affiliate_code`: string | null.

Hints expected from LLM

- `hints.required_blobs`: resolver keys (e.g., `product:p123`, `categories`) the runtime should hydrate before calling handlers.
- `hints.force_authoritative`: boolean; when true, perform authoritative ICE calls where needed.

Priority, merging and runtime rules (summary)

- The runtime respects the order of `intents`: the first intent is highest priority.
- If the first intent is a confirm/cancel/fallback, the runtime may execute it immediately.
- Merge rule for conflicting slots: keep earlier intent's value unless a later intent has confidence >= earlier_confidence + 0.1.
- Actionable threshold: confidence >= 0.5.

Runtime algorithm (high level)

1. Parse the validated JSON payload.
2. If `hints.required_blobs` present on an intent, call `resolve_required_blobs(...)` and apply CAS updates when hydrations arrive.
3. Normalize slots, dispatch to mapped handler, and apply returned `oob_patch` with `store.cas_update`.
4. Stop if a handler returns a `next_node` that forces a confirm gate.

Clarification / fallback behavior

- If a required slot is null/missing, handlers should respond with a concise `clarify` question requesting exactly one slot.
- LLM may return a `clarify` intent with a `slots` object describing the slot to fill and `candidates` to present.

Examples (minimal)

User: "2 apples, deliver to Riverside, pay with MTN"

```json
{
  "event_id": "evt-1",
  "session_id": "s1",
  "intents": [
    {"id": "add_item", "confidence": 0.96, "slots": {"product_name": "apples", "quantity": 2}, "hints": {"required_blobs": ["catalog:search:apples"]}},
    {"id": "select_delivery_option", "confidence": 0.90, "slots": {"fulfillment_type": "delivery", "address": {"street":"Riverside"}}},
    {"id": "select_payment_method", "confidence": 0.80, "slots": {"payment_method": "mtn"}}
  ],
  "next_action": "reply",
  "suggested_next_node": "confirm_order_gate",
  "diagnostics": {"nlp_latency_ms": 45}
}
```

Operational notes

- Include a small OOB summary in the prompt (cart items, last payment method, last executed node) to improve parsing.
- Validate JSON strictly; if invalid, fall back to the deterministic resolver.

Security & safety

- Do not include PII beyond what is strictly necessary in the prompt. Mask sensitive fields.
- Keep authoritative decisions (pricing, stock, payments) with ICE; the LLM must not be trusted for those.

# End of spec
