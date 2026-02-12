# Custom Bot Intent Context (Gemini) — Canonical + Unambiguous

Purpose
- This file is the **single source of truth** for what the Gemini LLM must extract from a user message.
- Output must be **machine-parseable JSON only**.
- Intent ids and slot names MUST match this document exactly.

## 1) LLM output contract (STRICT)
Return exactly one JSON object (no markdown, no prose):

```json
{
  "intents": [
    {
      "id": "string",
      "confidence": 0.0,
      "slots": {},
      "hints": {
        "required_blobs": [],
        "force_authoritative": false
      }
    }
  ],
  "next_action": "reply"
}
```

Rules
- `intents` MUST be a non-empty list, ordered **highest priority first**.
- `confidence` is 0..1 (float).
- `slots` is a map (string keys). Use `null` for unknown values.
- `hints` is optional. If present:
  - `required_blobs`: resolver keys (examples below).
  - `force_authoritative`: true only for pricing/stock/payment/order actions.
- `next_action` is one of: `reply` | `outbound` | `none`.

## 2) Runtime execution rules (node engine)
The bot runtime will:
1. Read `intents[]` in order.
2. **Preempt rule:** if the first intent is one of:
   - `confirm_payment`, `confirm_order`, `cancel`, `help`
   then execute it and stop.
3. Otherwise execute intents sequentially and apply each update via Redis CAS.
4. For intents that include `hints.required_blobs`, runtime calls `resolve_required_blobs(...)` before executing the handler.

## 3) Canonical intent ids (priority groups)

### Group 1 — Confirm / Cancel / Help (preemptive)
- `confirm_payment` (strict phrase)
- `confirm_order` (strict phrase)
- `cancel`
- `help`

### Group 2 — Authoritative backend actions (ICE)
- `order.calculate_total`
- `order.check_stock`
- `order.place_order`
- `payment.trigger_payment`
- `payment.verify_status`

### Group 3 — Cart operations
- `add_item`
- `remove_item`
- `clear_cart`
- `view_cart`
- `inspect_item`

### Group 4 — Fulfillment
- `select_delivery_option`
- `choose_location`
- `choose_fulfillment_method`

### Group 5 — Catalog browsing (cache-first + resolver)
- `serve_categories`
- `select_category`
- `serve_products`
- `select_product`
- `show_product_details`

### Group 6 — Affiliate tracking
- `capture_affiliate`
- `track_affiliate_click`

### Group 7 — Fallback
- `fallback_unknown_intent`

## 4) Slot schema per intent (what to extract)

### `add_item`
Slots:
- `product_name`: string|null (example: "apples")
- `quantity`: int|null (example: 2)
Optional:
- `product_id`: string|null (if the user explicitly references a known id/sku)
Extraction notes:
- Parse patterns like "2 apples", "x2 apples", "apples x2".
- Support multiple items in one message by emitting multiple `add_item` intents.
Hints:
- `required_blobs`: `["catalog:search:<product_name>"]` (optional)

### `remove_item`
Slots:
- `product_name`: string|null

### `clear_cart`
Slots: {}

### `view_cart`
Slots: {}

### `inspect_item`
Slots (one of):
- `line_index`: int|null (0-based) OR
- `product_name`: string|null

### `select_delivery_option`
Slots:
- `fulfillment_type`: "delivery"|"pickup"|null

### `choose_location`
Slots (one of):
- `address`: object|null (keys: `street`, `city`, `zone` when available)
- `pickup_location`: object|null

### `choose_fulfillment_method`
Slots:
- `method`: string|null (examples: "delivery_window", "pickup_time")
- `details`: object|null

### `select_payment_method`
Slots:
- `payment_method`: "mtn"|"airtel"|"card"|"cash"|null

### `serve_categories`
Slots: {}
Hints:
- `required_blobs`: `["categories"]` (optional)

### `select_category`
Slots:
- `category_id`: string|null
- `category_name`: string|null

### `serve_products`
Slots:
- `category_id`: string|null
- `category_name`: string|null
Hints:
- If category known: `required_blobs`: `["products:category:<category_id_or_name>"]`

### `select_product`
Slots:
- `product_id`: string|null
- `product_name`: string|null

### `show_product_details`
Slots:
- `product_id`: string|null
- `product_name`: string|null
Hints:
- If product_id known: `required_blobs`: `["product:<product_id>"]`

### `confirm_order`
Slots: {}
Strict phrase rule:
- Only emit when the full user message equals `CONFIRM ORDER` (case-insensitive).

### `confirm_payment`
Slots: {}
Strict phrase rule:
- Only emit when the full user message equals `CONFIRM PAYMENT` (case-insensitive).

### `capture_affiliate`
Slots:
- `affiliate_code`: string|null
- `source`: string|null

### `track_affiliate_click`
Slots:
- `affiliate_code`: string|null
- `source`: string|null

### `fallback_unknown_intent`
Slots: {}

## 5) Examples

User: "2 apples and 3 oranges"
```json
{
  "intents": [
    {"id":"add_item","confidence":0.95,"slots":{"product_name":"apples","quantity":2}},
    {"id":"add_item","confidence":0.93,"slots":{"product_name":"oranges","quantity":3}}
  ],
  "next_action":"reply"
}
```

User: "CONFIRM PAYMENT"
```json
{
  "intents": [
    {"id":"confirm_payment","confidence":0.99,"slots":{}}
  ],
  "next_action":"reply"
}
```
