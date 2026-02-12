## 4) Implementation phases (build in this order)

- [x] **order.validate_items**: Ensures every cart item has valid product refs/options.
- [x] **order.check_stock**: Calls ICE to validate/reserve stock (authoritative).

# Custom Bot Service — Implementation Guide (Simple + Detailed)

This document explains **what to build**, **in what order**, and **how to verify it works**.

If you’re new to microservices: think of this service like a **robot cashier**.

- It reads a customer message from a queue.
- It asks an “intent brain” what the user wants (intent-service).
- It updates the “shopping cart” (OOB = Order Object Builder).
- It sends a reply request to the reply service.

---

## Architecture rule (IMPORTANT)

This is the system rule you asked for. Keep it simple and strict:

- **ICE communicates with backend systems** (catalog, inventory, pricing, payments, orders, etc).
- **Bot services do NOT call backend directly.**
- **Bot services may talk to each other only when needed** (example: custom-bot-service → intent-service, custom-bot-service → reply-service).
- **Whenever a bot service needs backend data or backend actions, it calls ICE.**

This makes ICE the single “backend gateway” and keeps bot services consistent.

**Updated architecture path (must follow):**

- Ingress → custom/default bot → outbound
- ICE is the central backend entrypoint for all authoritative backend actions

---

## Strict Multi-Intent Execution (Checklist)

This checklist is written so a 10-year-old can follow it. Each step points to the file you should edit.

1) **Read the model response** (get stage, intents, diagnostics)

- Update the response parsing path in [app/runtime_engine.py](../app/runtime_engine.py).
- If you need to change how intents are parsed, adjust [app/intent_parser.py](../app/intent_parser.py).

1) **Turn intents into one simple list** (one list with stage + intent_id + slots)

- Add or update a helper in [app/runtime_engine.py](../app/runtime_engine.py) to flatten intents.

1) **Check the stage order rule** (chat → cart → order → payment → delivery → closed)

- Use the existing `STAGE_ORDER` and `INTENT_STAGE_MAP` in [app/runtime_engine.py](../app/runtime_engine.py).
- If an intent tries to jump forward, mark it as “deferred” or “rejected” and add a note to diagnostics.

1) **Use ICE for trusted data** (prices, stock, payment, delivery)

- ICE client lives in [app/ice_client.py](../app/ice_client.py).
- Cache/ICE resolver lives in [app/resolver.py](../app/resolver.py).
- Keep the contract docs in sync with [docs/ICE_CONTRACTS.md](ICE_CONTRACTS.md).

1) **Run intents in strict order** (do chat work first, then cart, then order, etc.)

- Sequence handling happens in [app/runtime_engine.py](../app/runtime_engine.py).
- Add or call stage-specific handlers from [app/handlers](../app/handlers).

1) **Update the cached state after each intent** (so the next intent sees fresh data)

- Use OOB updates in [app/oob_store.py](../app/oob_store.py).
- Record progress with [app/session_cycle.py](../app/session_cycle.py).

1) **Track missing fields** (record missing slots and why)

- Add missing fields into `diagnostics.missing` in [app/runtime_engine.py](../app/runtime_engine.py).
- Use the existing missing slot helpers in [app/runtime_engine.py](../app/runtime_engine.py).

1) **Finish with a clean reply plan** (what to say + next action)

- Reply planning lives in [app/runtime_engine.py](../app/runtime_engine.py).
- NLG fallbacks are in [app/nlg_renderer.py](../app/nlg_renderer.py).

1) **Write audit + telemetry** (so you can debug later)

- Audit calls in [app/audit_client.py](../app/audit_client.py).
- Metrics in [app/telemetry.py](../app/telemetry.py).

1) **Add tests for stage rules** (make sure you can’t skip forward)

- Add or extend tests in [tests/test_confirm_order_gate.py](../tests/test_confirm_order_gate.py) and
    [tests/test_confirm_payment_gate.py](../tests/test_confirm_payment_gate.py).
- Add a new test file if needed: [tests/test_stage_progression.py](../tests/test_stage_progression.py).

Tip: if a step feels too big, do it in tiny changes and run one test at a time.

---

## Affiliate performance tracking (bots track, backend computes)

You said you want to track affiliate performance.

Here is the rule (keep it strict):

- **Affiliate Engine is a backend service.**
- **Bot layer NEVER calls affiliate-engine directly.**
- **Bot layer only communicates with affiliate logic through ICE.**
- **Bot layer helps with tracking (capturing codes + emitting simple events), but does NOT compute affiliate payouts/tiers.**

### How soft-launch tracks affiliate performance (high level)

In soft-launch, affiliate performance is built from events like:

- `order_created` (contains `affiliate_code` when present)
- `payment_success` (contains earnings fields + `affiliate_code`)

Affiliate Engine also supports an append-only log of affiliate events for performance (examples: clicks, conversions, sales).

### What the bot layer should do

1) **Capture affiliate_code**

- If inbound payload contains an affiliate code (link/code/utm), store it in session context.

1) **Keep it attached to the order**

- When placing an order through ICE, always include `metadata.affiliate_code` if known.

1) **Track click/entry (optional but helpful)**

- If the bot is the first system that sees the affiliate code, it can ask ICE to record a `campaign_click` tracking event.

1) **Never compute affiliate logic**

- Do not calculate commission.
- Do not decide tiers/multipliers.
- Do not compute pool payouts.

### Where to store affiliate info (simple)

- Store in session context (Redis) and in OOB meta:
  - `oob.meta.affiliate_code`
  - (optional) `oob.meta.affiliate_source` ("link"|"utm"|"manual")

See affiliate JSON examples here:

- [bot services/affiliate_jsonb_examples.md](bot%20services/affiliate_jsonb_examples.md)

---

## 1) What this service is responsible for

**Input:** a stream message from Ingress on `bot:lane:custom`.

**Output:**

- Publish a reply request to `reply:requests`.
- Append an audit record to `oob:audit` (or reuse `ingress:resolved_payload` for replay).
- On failures: publish to `custom-bot:dlq`.

**State:**

- Session state in Redis (lightweight routing info).
- OOB (Order Object Builder) in Redis (the live “order/cart”).

---

## Cache-first behavior (Ingress-style) for handlers

You want handlers to behave like Ingress enrichment:

- **Cache-first:** read stable JSON documents from Redis first.
- **Call ICE only when needed:**
  - missing fields (not in cache),
  - authoritative fields (pricing, payment, reservation, stock locks),
  - or specific “triggers” (examples below).

### What “cache-first” means in practice

Before calling ICE, a handler should try to build its required input from cached/stable JSON blobs:

- `session:ctx:{session_id}` (session context)
- `user:core:{user_id}` (user profile)
- `bot:core:{bot_id}` (bot config)
- `cap:bundle:{capability_set_id}` (capabilities)
- `catalog:product:{product_id}` or similar stable catalog documents

If the handler still cannot proceed, it asks ICE to hydrate only what’s missing.

### When a handler MUST call ICE (authoritative actions)

These should always go through ICE even if you have cached data:

- price calculation / promotions / taxes
- inventory reservation / stock validation
- payment authorization / payment capture
- order creation / order status changes

Reason: these operations need “truth” from backend systems.

### When a handler MAY call ICE (missing fields)

Examples:

- the user said “add apples” but you don’t have a product id → ask ICE (or ICE-backed search) for product lookup
- the bot config is missing for this bot_id → ICE hydrate bot blob
- session context is missing `currency` or `locale` → ICE hydrate session context

### Suggested triggers that force re-hydration

Even if cache exists, you can force ICE hydration when:

- cache is older than TTL
- a previous ICE call returned partial data
- a handler detects inconsistent state (example: cart items exist but product blobs missing)

---

## Handler pattern: “Field Resolver” (recommended)

To make cache-first easy and consistent, implement a small resolver used by all handlers:

1. Handler declares what it needs (example: `product_core`, `pricing_quote`, `inventory_check`).
2. Resolver attempts to load the needed docs from Redis.
3. If something is missing (or authoritative), resolver calls ICE with a `required_blobs` list.
4. Resolver writes returned blobs back to Redis (unless Redis is read-only) and returns a unified view to the handler.

This keeps handler code clean and prevents “ICE calls everywhere”.

Recommended ICE request shape (conceptual):

- Input: `session_id`, `event_id`, and `required_blobs: ["session_context", "bot", "user", "catalog:product:123"]`
- Output: a dict of stable JSON blobs + optional refs/version

---

## Key decision: stable JSON blobs + refs

For big documents, avoid copying giant JSON into every message.

- Put large blobs in Redis under stable keys.
- In messages (reply/audit), pass **refs** (keys) like `oob:{session_id}` and `session:ctx:{session_id}`.
- Only include small summaries in the stream payload.

---

## 2) The message flow (end-to-end)

### Step-by-step (one message)

1. **Ingress publishes** an enriched envelope to `bot:lane:custom`.
2. **Custom-bot-service consumes** it.
3. It checks **idempotency** using `event_id` (don’t process same event twice).
4. It loads the session state + OOB (cart/order) from Redis.
5. If required, it calls **Intent Service via HTTP** to get `{intent, slots}`.
6. It chooses a handler (based on current node + intent).
7. The handler returns a **patch** (what changes to apply).
8. Custom-bot-service applies the patch safely (optimistic CAS / lock_version).
9. It publishes a reply job to `reply:requests`.
10. It writes an audit entry (`oob:audit`).

### Where ICE fits in this flow

ICE calls should happen inside the handler (or inside the shared resolver used by handlers):

- If cache has what you need → **no ICE call**.
- If missing non-authoritative data → ICE hydrate missing blobs.
- If authoritative action needed (price/payment/reserve) → ICE call even if cache exists.

---

## Fast checkout goal: finish in 3–5 messages

You said you want the bot to complete an order + payment in only **3–5 messages**, not a long “wizard”.

The trick is:

- Don’t force the user to go step-by-step.
- Let the user provide information **in any order**.
- Always update the cart/OOB immediately when you can.
- Only block on two strict confirmation moments:
  - **Confirm Order** (place the order)
  - **Confirm Payment** (charge the user)

### Example A: user says “Hi”

Message 1 (User): Hi

Message 2 (Bot):

- Greets
- Suggests popular + previously bought items
- Asks one short question: “What would you like today?”

Message 3 (User): 2 apples and 3 oranges

Message 4 (Bot):

- Creates cart immediately
- Shows short summary + asks missing requirements in one message (delivery/pickup, address, payment method)

Message 5 (User): Delivery, pay by card, use my last address

Message 6 (Bot):

- Shows final total
- Asks for strict confirmation word(s): “Reply **CONFIRM ORDER** to place order.”

Then:

- User: CONFIRM ORDER
- Bot: places order (ICE) and asks “Reply **CONFIRM PAYMENT** to pay …”
- User: CONFIRM PAYMENT
- Bot: pays (ICE) and returns receipt

### Example B: user gives everything in the first message

Message 1 (User): hey i want 2 apples and oranges, delivery to riverside, pay by mtn

Message 2 (Bot):

- Creates cart
- Sets delivery + payment preference
- Shows final summary
- Asks only for strict confirmation: “Reply **CONFIRM ORDER** …”

This is how you compress the flow.

---

## Slot-filling + confirm gates (how to design handlers/nodes)

Think of your bot as filling a checklist (“required fields”) instead of walking a strict path.

### Required fields (minimum to place an order)

You can treat these like a checklist:

- `cart.items[]` (must have at least 1 item)
- `fulfillment.type` = `delivery` or `pickup`
- If delivery: `delivery.address` (or address_ref)
- `payment.method` (momo/card/cash/etc)
- `order_confirmed` (only becomes true if user says CONFIRM ORDER)
- `payment_confirmed` (only becomes true if user says CONFIRM PAYMENT)

### The two strict confirmation intents (must be explicit)

No matter what the user says earlier, these must be explicit phrases:

- `confirm_order` intent: only when user message matches something like `CONFIRM ORDER`
- `confirm_payment` intent: only when user message matches something like `CONFIRM PAYMENT`

Everything else can be flexible.

### Suggested node names (simple, not restrictive)

Nodes are just labels to help the bot know what to ask next. The user can still jump around.

- `greet_and_suggest`
- `build_cart`
- `collect_fulfillment`
- `collect_payment_method`
- `confirm_order_gate`
- `confirm_payment_gate`
- `done`

Rule of thumb:

- On every message, try to apply intents to the OOB (cart, delivery, payment prefs).
- After applying, compute `missing_fields` and ask for them.
- If nothing missing, move to confirm gate.

### Multi-intent in one message

One user message can contain multiple actions:

- “2 apples, deliver to X, pay by mtn”

This should result in multiple intents like:

- `add_item` (apples, qty=2)
- `set_delivery` (location=X)
- `set_payment_method` (method=mtn)

Apply them in order, then ask only what is still missing.

### What “idempotency” means

If the same `event_id` arrives twice (retries happen in real systems), you must:

- detect it,
- skip re-running side effects,
- return/publish the already-produced result.

---

## 3) Data contracts (keep these small and stable)

### 3.1 Input envelope (from Ingress)

Minimum fields you should rely on:

- `event_id` (stable ID)
- `session_id`
- `payload` JSON (enriched payload)
- `meta.routing_hints.intent_required`
- `meta.session.bot_type` = `custom`

### 3.2 Intent result (from intent-service)

The custom bot should treat this as the “user’s goal”:

- `id` (e.g. `add_item`)
- `confidence`
- `slots` (e.g. `{ "quantity": 2, "product_name": "apples" }`)

### 3.3 OOB (Order Object Builder)

Start with a minimal JSON shape that you can grow:

```json
{
  "schema_version": "v1",
  "lock_version": 1,
  "last_event_id": null,
  "last_node_executed": null,
  "cart": {
    "items": [],
    "totals": {"subtotal": 0, "grand_total": 0},
    "status": "building",
    "cart_version": 1
  },
  "meta": {}
}
```

### 3.4 ICE usage contract (for bots)

Bots should treat ICE as:

- **Hydrator** for stable JSON blobs (cache fill / missing fields)
- **Authority** for backend actions (pricing, inventory reserve, payments, order create)

Bots should NOT call backend services directly.

---

## 4) Implementation phases (build in this order)

### Phase A — “Just consume and log” (foundation)

Goal: prove you can read `bot:lane:custom` reliably.

Checklist:

- [x] Read from Redis Streams with `XREADGROUP` (consumer group like `custom-bot-workers`).
- [x] Parse `payload` JSON safely.
- [x] Log `event_id`, `session_id`, and `bot_type`.
- [x] Ack messages only after you finish processing.
- [ ] On errors: retry with backoff, then DLQ after N attempts. (DLQ + attempt counting exists, but true retry for pending entries is still TODO)

### Phase B — Add idempotency

Goal: avoid double processing.

Checklist:

- [x] Use key `idempotency:custombot:{event_id}`.
- [ ] Only mark done after reply + audit publish succeed. (currently marked done after Phase-A logging)
- [x] If duplicate: ack and skip.

### Phase C — Add sync HTTP call to intent-service

Goal: resolve intents fast.

Checklist:

- [ ] Build an HTTP client with timeouts.
- [ ] Send: `event_id`, `session_id`, `raw_text`, and small context.
- [ ] Respect `routing_hints.intent_required`.
- [ ] If intent-service fails or returns empty: fall back to a safe default intent.

### Phase D — Add OOB read/write

Goal: maintain a cart/order state.

Checklist:

- [x] Key OOB by `session_id` (e.g. `oob:{session_id}`).
- [x] Read OOB from Redis (best-effort). If missing, a default OOB shape is returned.
  - [x] If missing, create and persist default OOB.
  - [x] Use `lock_version` or `cart_version` for optimistic writes. (CAS store exists, but handlers/engine don’t apply patches yet)
  - [x] Update `last_event_id` after successful apply.

### Phase E — Implement handler interface

Goal: move business logic into handlers.

Checklist:

- [ ] Define a handler input object (event + intent + oob snapshot + meta).
  - [x] Add a shared **resolver** used by handlers for cache-first loading + ICE hydration.
- [ ] Handler declares `required_fields` / `required_blobs` (inputs it needs).
- [ ] Handlers return:
  - `node_executed`
  - `action_status` (`success|fail`)
  - `oob_patch` (list of ops)
  - `next_node`
  - `diagnostics`
  - [x] Node engine applies patch atomically.

### Phase E2 — Add ICE client (cache-first + authoritative)

Goal: make ICE usage consistent across handlers.

Checklist:

- [x] Implement `IceClient.hydrate(required_blobs, session_id, event_id, hints)`.
- [x] Implement resolver logic: Redis read → decide missing/authoritative → ICE call → Redis write.
- [x] Add negative caching (short TTL) for “not found” blobs to avoid repeated ICE calls.
- [x] Add a single-flight lock per session (avoid multiple workers hydrating same session at once).

### Phase E extras — runtime improvements

- [x] Add single-flight in-process hydration locking in `app/resolver.py` (prevents duplicate concurrent hydrations within a process).
- [x] Add integration test `tests/test_resolver_singleflight.py` verifying single-flight behavior.

### Phase F — Publish reply request

Goal: let reply-service render user-facing responses.

Checklist:

- [x] Publish to `reply:requests` with:
- `event_id`, `session_id`
- chosen `next_node`
- minimal reply hints
- references (OOB key/ref), not a giant payload

Note: the publishing flow is implemented in `app/processor.py` (calls `process_event`) and `app/publish.py` (`publish_reply_request` and `publish_audit`).

### Phase G — Audit + observability

Goal: easy debugging.

Checklist:

- [ ] Append audit record to `oob:audit` (event_id + patch + diagnostics).
- [ ] Log structured events: `node_enter`, `node_exit`, `intent_call`, `oob_apply`.
- [ ] Track latency (timers) and failure counters.

Status: partially implemented — audit publishing exists (`app/publish.py` + `app/processor.py`).
Added a small telemetry helper (`app/telemetry.py`) and `processor.py` now emits a `message_processed` structured event and increments simple metrics keys.

Resolver & handler migration status:

- `app/resolver.py` now supports cache-first hydration for `product:{id}` keys, including negative caching and in-process single-flight locking.
- Most handlers in `app/handlers/` use the shared `resolve_required_blobs` API for non-authoritative hydration; only authoritative operations (pricing, stock reservation, order creation, payment operations) continue to call ICE directly as designed.
- Remaining: review any handler that still performs non-authoritative ICE calls and convert them to resolver-based hydration where appropriate.

Telemetry enhancements completed:

- Node-level `node_enter` / `node_exit` events implemented (`app/runtime_engine.py`) with non-blocking writes.
- Telemetry events include `trace_id` and `span_id` for cross-service correlation.
- Telemetry sampling is configurable via `CUSTOM_BOT_TELEMETRY_SAMPLING_RATE` (default=1.0).
- Metrics use Redis counters (existing `app/telemetry.py::incr_metric`) to keep integration simple; these writes are scheduled asynchronously to avoid added latency.

Remaining telemetry options: hook a central consumer to export events to Prometheus/StatsD, or add a dedicated metrics exporter service.

---

## 5) Suggested folder layout (practical)

You can keep the code organized like this:

- `app/worker.py` — reads `bot:lane:custom`, retries, DLQ
- `app/intent_client.py` — HTTP client to intent-service
- `app/oob_store.py` — get/set OOB with CAS
- `app/engine.py` — chooses handler, applies patch
- `app/resolver.py` — cache-first loader + decides ICE calls
- `app/ice_client.py` — calls ICE (hydrate + authoritative operations)
- `handlers/` — business logic per node/intent
- `events/` — audit/reply message builders

---

## 6) Testing plan (small but powerful)

### Unit tests

Checklist:

- [ ] Handler tests: given OOB + intent → patch + next_node.
- [ ] OOB store tests: version conflict handling.
- [ ] Intent client tests: timeout/fallback.
- [ ] Resolver tests: cache-hit (no ICE) vs cache-miss (ICE called).
- [ ] ICE client tests: timeout/retry + safe failure behavior.

### Integration tests (local Redis)

Checklist:

- [ ] Push a fake enriched envelope to `bot:lane:custom`.
- [ ] Verify a reply job appears on `reply:requests`.
- [ ] Verify OOB was updated.
- [ ] Verify an audit record was written.

---

## 7) “Definition of Done” (DoD)

Your Custom Bot Service is “done” when:

- [ ] It consumes from `bot:lane:custom` continuously.
- [ ] It never double-processes the same `event_id`.
- [ ] It calls intent-service (sync HTTP) and uses the result.
- [ ] It updates OOB safely and predictably.
- [ ] It publishes reply jobs and audit records.
- [ ] It has DLQ + basic metrics/logs.
- [ ] It has unit + integration tests.

---

## 8) Quick start checklist (the fastest path)

If you only do 5 things first:

- [x] Implement Redis stream consumer for `bot:lane:custom`.
- [ ] Implement HTTP intent call (with timeout + fallback).
- [x] Implement OOB load keyed by `session_id` (store exists; save/apply comes with handlers).
- [x] Implement one handler: `add_item`.
- [ ] Publish one reply request to `reply:requests`.

---

## 9) Handler inventory (what to implement next)

These are the handlers you’ll need for the flows described in the `handlers/` intent trees and in this document.

Think of a handler as a function that:

- takes `(event + intent + oob snapshot + session context)`
- applies a small OOB update (via CAS)
- returns: `next_node` + `reply_hints`

### Customer mode (shopping)

- [x] **greet_and_suggest**: Greets user, loads “top items / last purchased” (cache-first), proposes quick options.
- [x] **browse_catalogue.serve_categories**: Shows available categories (cache-first; ICE hydrate categories if missing).
- [x] **browse_catalogue.select_category**: Saves selected category to session/OOB, moves to product listing.
- [x] **browse_catalogue.serve_products**: Lists products for a category (cache-first; ICE search if missing).
- [x] **browse_catalogue.select_product**: Saves selected product_id/sku in context.
- [x] **browse_catalogue.show_product_details**: Shows price/description; calls ICE for authoritative pricing if needed.
- [x] **browse_catalogue.show_product_details**: Shows price/description; calls ICE for authoritative pricing if needed.

- [x] **cart.add_item**: Adds one item (qty + product_id/sku) into `oob.cart.items[]`; if product_id missing, resolve via ICE search.
- [x] **cart.remove_item**: Removes an item from cart.
- [x] **cart.clear**: Clears the cart.
- [x] **cart.view**: Builds a small cart summary response (items + subtotal) from OOB.
- [x] **cart.inspect_item**: Shows details for a single cart line (qty, unit price, options).

- [x] **order.confirm_cart**: Validates cart is placeable (has items, sane quantities) and moves to totals/fulfillment.
- [x] **order.validate_items**: Ensures every cart item has valid product refs/options.
- [x] **order.validate_items**: Ensures every cart item has valid product refs/options.
- [x] **order.check_stock**: Calls ICE to validate/reserve stock (authoritative).
- [x] **order.calculate_total**: Calls ICE to price the cart (tax/discounts/promotions; authoritative).
- [x] **order.review_order**: Shows final order summary (items, totals, fulfillment, payment method) and routes to confirm gate.

- [x] **fulfillment.select_delivery_option**: Chooses `delivery` vs `pickup` into OOB.
- [x] **fulfillment.choose_location**: Sets delivery address or pickup location; uses saved address_ref if available.
- [x] **fulfillment.select_delivery_option**: Chooses `delivery` vs `pickup` into OOB.
- [x] **fulfillment.choose_location**: Sets delivery address or pickup location; uses saved address_ref if available.
- [x] **fulfillment.choose_method**: Sets fulfillment method details (delivery window, pickup time slot, notes).

- [x] **contact.enter_phone_number**: Captures phone number (or uses cached user profile via ICE if missing).
- [x] **contact.enter_name**: Captures name (or uses cached user profile via ICE if missing).

- [x] **payment.select_payment_method**: Sets payment method (mtn/airtel/zamtel/card/cash) in OOB.

- [x] **confirm_order_gate**: Strictly checks user text equals the confirm phrase (e.g. `CONFIRM ORDER`) before calling ICE order-create.
- [x] **order.place_order**: Calls ICE to create the order (authoritative). Stores `order_id` and status in OOB.
- [x] **confirm_payment_gate**: Strictly checks user text equals the confirm phrase (e.g. `CONFIRM PAYMENT`) before charging.
- [x] **payment.trigger_payment**: Calls ICE to initiate payment (authoritative).
- [x] **payment.verify_status**: Calls ICE to poll/confirm payment status until success/fail/timeout.

- [x] **notify_user**: Formats a short receipt + delivery/pickup instructions and moves node to `done`.

### Affiliate tracking (cross-cutting)

- [x] **affiliate.capture_code**: Extracts `affiliate_code` from inbound payload and stores into `oob.meta.affiliate_code`.
- [x] **affiliate.capture_code**: Extracts `affiliate_code` from inbound payload and stores into `oob.meta.affiliate_code`.
- [x] **affiliate.track_click (optional)**: If this is the first event with the code, ask ICE to record `campaign_click`.

### Staff mode (MSME)

- [ ] **staff.authenticate_user.send_otp**: Requests OTP via ICE.
- [ ] **staff.authenticate_user.verify_otp**: Verifies OTP via ICE and marks session as authenticated.

- [ ] **staff.analytics.view_sales**: Loads sales metrics via ICE (authoritative backend data).
- [ ] **staff.analytics.view_orders**: Loads order list/status via ICE.
- [ ] **staff.analytics.view_traffic**: Loads traffic metrics via ICE.

- [ ] **staff.product.add.submit_product_* (name/category/price/stock/description/image_url)**: Slot-filling handlers that build a product draft in session/OOB.
- [ ] **staff.product.add.confirm_product_details**: Shows the draft and asks for confirmation.
- [ ] **staff.product.add.save_product**: Creates product via ICE (authoritative).

- [ ] **staff.product.edit.view_product_list_for_edit**: Lists products via ICE.
- [ ] **staff.product.edit.select_product_to_edit**: Saves selected product id.
- [ ] **staff.product.edit.choose_field_to_update**: Determines which field to update.
- [ ] **staff.product.edit.update_product_* (name/category/price/stock/description/image_url)**: Applies field update to product draft.
- [ ] **staff.product.edit.confirm_product_update**: Shows changes + asks for confirmation.
- [ ] **staff.product.edit.save_product_changes**: Saves edits via ICE (authoritative).

- [ ] **staff.product.remove.view_product_list_for_removal**: Lists products.
- [ ] **staff.product.remove.add_to_removal_cart / remove_from_removal_cart / clear_removal_cart**: Manages a removal list.
- [ ] **staff.product.remove.confirm_removal_cart**: Confirms deletion intent.
- [ ] **staff.product.remove.delete_selected_products**: Deletes via ICE (authoritative).

- [ ] **staff.product.view_product_list**: Lists products for viewing (ICE).
- [ ] **staff.product.list_all_products**: Paginates/filters through product list (ICE).
- [ ] **staff.product.view_product_summary**: Shows key info for a selected product (price/stock/status).

- [ ] **staff.profile.update_* (business_name/business_type/location/establishment_year/contact_info)**: Updates business profile via ICE.

- [ ] **staff.staff.add.submit_staff_* (name/phone/position)**: Slot-filling for staff creation.
- [ ] **staff.staff.add.confirm_staff_details**: Confirms staff details.
- [ ] **staff.staff.add.save_staff_member**: Creates staff member via ICE.
- [ ] **staff.staff.remove.view_staff_list_for_removal / select_staff_to_remove / confirm_staff_removal**: Removal flow.
- [ ] **staff.staff.remove.delete_staff_member**: Deletes staff via ICE.
- [ ] **staff.staff.view_staff_list**: Lists staff.
- [ ] **staff.staff.view_staff_summary**: Shows details for one staff member.

### System/fallback handlers (must-have)

- [x] **help**: Returns short help text and examples (“2 apples”, “delivery”, “pay by mtn”, “CONFIRM ORDER”).
- [x] **cancel**: Cancels current flow and (optionally) clears draft state.
- [x] **fallback_unknown_intent**: Safe default when intent-service fails; asks one clarifying question.
- [ ] **handoff_to_human (optional)**: Emits a handoff request to support channel.
