# Bot Intent Service — Implementation Guide (Simple + Detailed)

This guide explains how to make the intent service support a **fast checkout** conversation (3–5 messages) by producing **multi-intent + slots** with clear confirmation rules.

If you’re new to microservices: think of this service as the **“intent brain”**.
- Bots send it a user message + small context.
- It returns a clean JSON result: “what the user wants” + details (slots).

---

## 1) The goal (what we want to achieve)

We want conversations like:

User: “hey i want 2 apples and oranges, delivery to riverside, pay by mtn”

…to be understood in one shot and returned as multiple intents:
- add items
- set delivery
- set payment method

And we want strict confirmations:
- placing the order only when the user says **CONFIRM ORDER**
- charging payment only when the user says **CONFIRM PAYMENT**

---

## 2) Architecture rule (IMPORTANT)

- **Bot services do NOT call backend directly.**
- If bots need backend actions/data, they call **ICE**.
- The intent service is a bot service: it only analyzes text + context and returns JSON.

---

## 3) What the code does today (current behavior)

### Main file
- The core logic is in app/services/intent_service.py.

### Output shape
The prompt forces Gemini to output strict JSON with this shape:

- top-level key "intents" (array)
- each intent: {"id": string, "name": string|null, "confidence": number, "slots": object}
- optional top-level "next_action": "reply"|"outbound"|"none"

The response model already supports multi-intent:
- app/models/schemas.py → IntentResponse has both:
  - intent (first/primary)
  - intents (list of DetectedIntent)

### Context summarizer
- app/services/summarizer.py builds a small context string from request.enriched_meta.
It can include:
- current_node/state
- cart/order draft summary
- user first name
- last 1–2 turns of history (if present)

---

## 4) The most important thing: reduce ambiguity with better context

LLMs become confused when they don’t know:
- what stage the user is in
- what items are already in cart
- what “confirm” should mean
- what options are allowed (payment methods, delivery vs pickup)

So bots must send a small but strong context in IntentRequest.enriched_meta.

### Minimum context to send (recommended)
Put these fields in enriched_meta (simple JSON):

1) Conversation state
- current_node (example: "collect_payment_method")
- missing_fields (example: ["payment.method", "delivery.address"])

2) Cart summary (not the full cart)
- order_draft.items (only names/ids + quantity)

3) Confirmation rules (very important)
- confirm_order_phrases: ["CONFIRM ORDER"]
- confirm_payment_phrases: ["CONFIRM PAYMENT"]

4) Allowed options (to avoid guessing)
- allowed_payment_methods: ["mtn", "airtel", "card", "cash"]
- allowed_fulfillment_types: ["delivery", "pickup"]

5) User preferences (if you have them)
- last_used_payment_method
- last_delivery_area

This context helps Gemini stop hallucinating and stop asking extra questions.

---

## 5) Intent set for a 3–5 message checkout

Keep intents small and reusable. Suggested intent ids:

### Cart intents
- add_item (slots: product_name|product_id, quantity)
- remove_item (slots: product_name|product_id, quantity?)
- set_quantity (slots: product_name|product_id, quantity)

### Fulfillment intents
- set_fulfillment (slots: type=delivery|pickup)
- set_delivery_address (slots: address_text|address_ref)
- set_delivery_time (slots: time_window)

### Payment intents
- set_payment_method (slots: method)

### Strict confirmation intents
- confirm_order (slots: none)
- confirm_payment (slots: none)

### Other
- greet
- help
- cancel

Key rule:
- confirm_order and confirm_payment should only be returned when the user text matches the allowed phrases.

---

## 6) Prompt rules (how to talk to Gemini)

Your current code already does the big rule correctly:
- RETURN ONLY JSON (no markdown, no explanation)

To further reduce ambiguity, the instruction should also say:

- Do NOT invent product ids, addresses, or payment tokens.
- If a value is missing, leave it out.
- Only emit confirm_order / confirm_payment when the user literally confirmed.

### Keep output short (so multi-intent fits)
Multi-intent needs more output tokens.

If you want 3–5 message flows, set:
- INTENT_GEMINI_MAX_OUTPUT_TOKENS=150

Why:
- output token limit 50 can be too small for 3–6 intents.

---

## 7) What the bot should send to intent service (example)

Example request (conceptual):

- raw_text: "2 apples and oranges, delivery to riverside, pay by mtn"
- enriched_meta:
  - current_node: "build_cart"
  - missing_fields: ["fulfillment.type", "payment.method"]
  - order_draft: { items: [] }
  - allowed_payment_methods: ["mtn", "airtel", "card", "cash"]
  - allowed_fulfillment_types: ["delivery", "pickup"]
  - confirm_order_phrases: ["CONFIRM ORDER"]
  - confirm_payment_phrases: ["CONFIRM PAYMENT"]

This gives Gemini enough information to confidently return:
- add_item intents
- set_fulfillment intent
- set_payment_method intent

---

## 8) How the bot should use the intent response

The intent service returns a list of intents in order.
The custom bot should:

1) Loop through response.intents in order
2) Apply each intent to the OOB
3) Compute missing fields
4) If missing fields exist → ask for them
5) If none missing → ask for CONFIRM ORDER
6) Only after CONFIRM ORDER → call ICE to place order
7) Only after CONFIRM PAYMENT → call ICE to charge payment

---

## 9) Testing checklist (simple but powerful)

### Unit tests (intent service)
- User text contains multiple actions → returns multiple intents
- Confirm phrases:
  - "CONFIRM ORDER" → returns confirm_order
  - "yes" → must NOT return confirm_order

### “Ambiguity” tests
- User: "pay" without method → should return set_payment_method intent with empty/partial slots (or no slot)
- User: "deliver" without address → should return set_fulfillment(type=delivery) but not invent address

### Output validity tests
- Always valid JSON
- Always includes top-level "intents" array

---

## 10) Quick config reference

Environment variables used by the current code:
- INTENT_GEMINI_ENABLED
- INTENT_GEMINI_API_KEY
- INTENT_GEMINI_MODEL
- INTENT_GEMINI_MAX_INPUT_TOKENS
- INTENT_GEMINI_MAX_OUTPUT_TOKENS
- INTENT_GEMINI_TIMEOUT_SECONDS

Recommended for multi-intent checkout:
- INTENT_GEMINI_MAX_OUTPUT_TOKENS=150
