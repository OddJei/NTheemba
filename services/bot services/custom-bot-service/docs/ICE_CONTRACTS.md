# ICE Contracts — Implemented Handlers

Purpose: describe ICE endpoints, request/response contracts, and ICE-side actions relevant to handlers already implemented in this service. Scope is limited to handlers currently present in `app/handlers`.

**Implemented handlers covered**:
- `cart.add_item`
- `cart.remove_item`
- `cart.clear`
- `cart.view`
- `cart.inspect_item`
- `order.confirm_cart`
- `help`, `cancel`, `fallback_unknown_intent`

---

## Summary (cache-first rule)

- All implemented handlers are cache-first and, in the current code, do not call ICE for authoritative actions. This document records the cache JSON blobs these handlers expect and the minimal ICE contracts to use when a handler needs hydration in the future.

---

## Cache JSON blobs (keys and expected shapes)

- `oob:{session_id}` (Order Object Builder) — canonical shape used by handlers:

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

- `session:ctx:{session_id}` — session context used for routing and defaults:

```json
{
  "session_id": "s123",
  "user_id": "u123",
  "bot_id": "botx",
  "locale": "en-ZM",
  "currency": "ZMW",
  "created_at": "2026-01-01T12:00:00Z",
  "affiliate_code": null
}
```

- `user:core:{user_id}` — minimal user profile that handlers may read:

```json
{
  "user_id": "u123",
  "name": "Jane Doe",
  "default_address_ref": "addr:1",
  "saved_payment_methods": [ {"id":"pm_1","type":"momo"} ]
}
```

- `bot:core:{bot_id}` — bot configuration used for suggestions / quick items:

```json
{
  "bot_id": "botx",
  "name": "ShopBot",
  "capabilities": ["cart","checkout"],
  "top_items": ["Apple","Bread"]
}
```

- `catalog:product:{product_id}` — product core (ICE-provided when hydration is needed):

```json
{
  "product_id": "p123",
  "name": "Apples",
  "description": "Fresh apples",
  "price": 1000,
  "currency": "ZMW",
  "available": true,
  "attributes": {"unit":"kg"}
}
```

---

## Handler-by-handler ICE notes (implemented handlers)

Note: the current implementation of these handlers does not call ICE. The contracts below are minimal suggestions for future hydration/authoritative calls; handlers remain cache-first and ICE should only be called when data is missing or an authoritative action is required.

- `cart.add_item`
  - Current behavior: merges item into `oob.cart.items[]` by `product_name`; no ICE calls.
  - Possible future ICE calls (when product id / SKU is required):
    - Endpoint: `POST /ice/catalog/search` or `GET /ice/catalog?query={q}`
    - Request: { "session_id", "query": "apples", "limit": 5 }
    - Response: [ {"product_id","name","canonical_name","primary_price":{"amount","currency"},"available"} ]
    - ICE action: return product_core blobs and optionally write a `catalog:product:{product_id}` stable blob.

- `cart.remove_item`
  - Current behavior: removes matching item(s) from `oob.cart.items[]` by product_name.
  - ICE: none required. If handler needs authoritative product info for logging or audit, ICE can return `catalog:product:{product_id}` via the same `GET /ice/catalog` contract above.

- `cart.clear`
  - Current behavior: resets cart to empty in OOB. No ICE calls.

- `cart.view`
  - Current behavior: builds a small cart summary from `oob.cart` and returns counts/totals (totals currently derived from OOB, not authoritative).
  - ICE (optional for totals/pricing): `POST /ice/cart/price` (see suggested `order.calculate_total` contract below). Not called by implemented handler.

- `cart.inspect_item`
  - Current behavior: read-only lookup in `oob.cart.items[]` (by `product_name` or index). No ICE calls.
  - Future authoritative lookup: `GET /ice/product/{product_id}`
    - Response: `catalog:product` JSON (see cache shape above)
    - ICE action: return authoritative unit price and availability.

- `order.confirm_cart`
  - Current behavior: local validations only (items present, quantities > 0). Marks `oob.cart.status = "ready_for_review"` on success. No ICE calls.
  - Important: this handler intentionally does not perform price calculation or stock reservation. Those authoritative actions are the responsibility of `order.calculate_total` / ICE.

- `help`, `cancel`, `fallback_unknown_intent`
  - Purely local, no ICE calls.

---

## Suggested minimal ICE endpoints (for future use)

- `GET /ice/catalog?query={q}`
  - Purpose: catalog search/hydration for product lookup.
  - Request: query param `q`; headers: `X-Session-Id`, optional `X-Event-Id`.
  - Response: 200 JSON array of product summaries.

- `GET /ice/product/{product_id}`
  - Purpose: authoritative product details for display or checkout.
  - Response: `catalog:product` JSON.

- `POST /ice/cart/price` (authoritative pricing)
  - Purpose: calculate totals, taxes, discounts, promotions.
  - Request: { "session_id": "s1", "oob_ref": "oob:s1" } or full cart lines.
  - Response: { "subtotal": 1200, "tax": 120, "discount": 0, "grand_total": 1320, "lines": [ {"product_id","unit_price","quantity","line_total"} ] }
  - ICE action: may also return `catalog:product` blobs to be persisted into Redis for cache-fill.
  - Handler behavior: `order.calculate_total` (implemented) will call this endpoint and persist the returned totals into `oob.cart.totals` and set `oob.cart.status = 'priced'` on success. On failure the handler will set `oob.last_validation_error = 'pricing_failed'`.

- `POST /ice/order/create` (order creation)
  - Purpose: create an order in backend systems using the authoritative ICE gateway.
  - Request: `{ "session_id": "s1", "oob_ref": "oob:s1", "affiliate_code": "ABC123" }` (affiliate_code optional)
  - Response (200): `{ "order_id": "ord_123", "status": "created", "eta": "2026-01-24T12:00:00Z" }`
  - Handler behavior: `confirm_order_gate` (implemented) will call this endpoint and persist `oob.meta.order_id`, `oob.meta.order_status`, and set `oob.cart.status = 'order_created'`. On ICE failure the handler will set `oob.last_validation_error = 'order_create_failed'`.
  
  Example cURL (replace base URL):

  ```bash
  curl -s -X POST \
    -H "Content-Type: application/json" \
    -H "X-Session-Id: s1" \
    -H "X-Event-Id: e1" \
    -d '{"session_id":"s1","oob_ref":"oob:s1","affiliate_code":"ABC123"}' \
    "https://ice.internal/ice/order/create"
  ```

  Successful response (200):

  ```json
  {
    "order_id": "ord_123",
    "status": "created",
    "eta": "2026-01-24T12:00:00Z"
  }
  ```

- `POST /ice/payment/trigger` (payment trigger)
  - Purpose: initiate/authorize payment for an order/cart.
  - Request: `{ "session_id": "s1", "oob_ref": "oob:s1", "payment_method": "momo" }`
  - Response (200): `{ "payment_id": "pay_1", "status": "initiated" }` or `{ "payment_id": "pay_2", "status": "paid" }`
  - Handler behavior: `confirm_payment_gate` (implemented) will call this endpoint and persist `oob.meta.payment_id`, `oob.meta.payment_status`, and set `oob.cart.status` accordingly (`payment_initiated` or `paid`). On ICE failure the handler will set `oob.last_validation_error = 'payment_trigger_failed'`.

  Example cURL (replace base URL):

  ```bash
  curl -s -X POST \
    -H "Content-Type: application/json" \
    -H "X-Session-Id: s1" \
    -H "X-Event-Id: e1" \
    -d '{"session_id":"s1","oob_ref":"oob:s1","payment_method":"momo"}' \
    "https://ice.internal/ice/payment/trigger"
  ```

  Successful response (200):

  ```json
  { "payment_id": "pay_1", "status": "initiated" }
  ```

  ---

  ## Intent mapping: payment.verify_status

  - **Intent name:** `payment.verify_status` (also accepted: `payment.verify`, `verify_payment`)
  - **Handler:** `payment_verify_status` (app/handlers/payment_verify_status.py)
  - **What it does:** runtime will call the handler to read `oob.meta.payment_id`, call ICE `POST /ice/payment/status`, and persist `oob.meta.payment_status` and update `oob.cart.status` accordingly.
  - **When to use:** after `payment.trigger_payment` to poll or confirm payment outcome, or when the user asks to check payment status.
  - **Expected ICE endpoint:** `POST /ice/payment/status` (see example above).

  Example incoming envelope for worker (conceptual):

  ```json
  {
    "event_id": "evt-123",
    "session_id": "s1",
    "raw_text": "check payment",
    "meta": { "intent_hints": ["payment.verify_status"] }
  }
  ```

  Handler side-effect: on success the handler persists `oob.meta.payment_status` (e.g. `paid`|`initiated`) and writes a reply/audit via the usual publish channels.

- `POST /ice/payment/status` (payment status)
  - Purpose: return current payment status for a payment id.
  - Request: `{ "payment_id": "pay_1", "session_id": "s1" }`
  - Response (200): `{ "payment_id": "pay_1", "status": "initiated" }` or `{ "payment_id": "pay_1", "status": "paid" }`

  Example cURL:

  ```bash
  curl -s -X POST \
    -H "Content-Type: application/json" \
    -H "X-Session-Id: s1" \
    -H "X-Event-Id: e1" \
    -d '{"payment_id":"pay_1","session_id":"s1"}' \
    "https://ice.internal/ice/payment/status"
  ```

- `POST /ice/fulfillment/validate` (fulfillment method validation)
  - Purpose: validate whether the chosen fulfillment method and details are acceptable (delivery windows, pickup location availability, etc.).
  - Request: `{ "session_id": "s1", "method": "delivery", "details": {"window":"morning"} }`
  - Response (200): `{ "valid": true }` or `{ "valid": false, "reason": "no_slots" }`

  Example cURL:

  ```bash
  curl -s -X POST \
    -H "Content-Type: application/json" \
    -H "X-Session-Id: s1" \
    -H "X-Event-Id: e1" \
    -d '{"session_id":"s1","method":"delivery","details":{"window":"morning"}}' \
    "https://ice.internal/ice/fulfillment/validate"
  ```

  ---

  ## Recommendations endpoint (used by greet_and_suggest)

  - `POST /ice/recommendations`
    - Purpose: return quick, cacheable recommendations or top-items for a session/bot.
    - Request: `{ "session_id": "s1", "count": 3 }` (JSON body)
    - Response (200): `{ "items": [ { "id": "p123", "title": "Apples", "product_id": "p123" }, ... ] }`
    - Notes: this endpoint may return cached suggestions and is suitable for non-authoritative UI hints (no stock/reservation). Handlers should treat results as ephemeral suggestions.

  Example cURL:

  ```bash
  curl -s -X POST \
    -H "Content-Type: application/json" \
    -H "X-Session-Id: s1" \
    -d '{"session_id":"s1","count":3}' \
    "https://ice.internal/ice/recommendations"
  ```

  Successful response (200):

  ```json
  { "items": [ { "id": "p1", "title": "Apples" }, { "id": "p2", "title": "Bananas" } ] }
  ```

  ---

  ## Categories endpoint (used by browse_catalogue.serve_categories)

  - `POST /ice/categories`
    - Purpose: return top-level categories or filtered categories for a session/bot.
    - Request: `{ "session_id": "s1", "limit": 10 }` (JSON body)
    - Response (200): `{ "categories": [ { "id": "c1", "name": "Fruits" }, ... ] }`
    - Notes: responses are suitable for UI suggestions and are non-authoritative. Handlers should treat results as hints and may fall back to cached bot config.

  Example cURL:

  ```bash
  curl -s -X POST \
    -H "Content-Type: application/json" \
    -H "X-Session-Id: s1" \
    -d '{"session_id":"s1","limit":10}' \
    "https://ice.internal/ice/categories"
  ```

  Successful response (200):

  ```json
  { "categories": [ { "id": "c1", "name": "Fruits" }, { "id": "c2", "name": "Bakery" } ] }
  ```

  ---

  ## Products endpoint (used by browse_catalogue.serve_products)

  - `POST /ice/products`
    - Purpose: return products for a category or search term.
    - Request: `{ "session_id": "s1", "category": "c1", "limit": 20 }` (JSON body)
    - Response (200): `{ "products": [ { "id": "p1", "name": "Apples", "price": 1000 }, ... ] }`
    - Notes: responses are non-authoritative and for display; authoritative pricing should use `POST /ice/cart/price`.

  Example cURL:

  ```bash
  curl -s -X POST \
    -H "Content-Type: application/json" \
    -H "X-Session-Id: s1" \
    -d '{"session_id":"s1","category":"c1","limit":10}' \
    "https://ice.internal/ice/products"
  ```

  Successful response (200):

  ```json
  { "products": [ { "id": "p1", "name": "Apples", "price": 1000 }, { "id": "p2", "name": "Bananas", "price": 500 } ] }
  ```

  ---

  ## Product detail endpoint (used by browse_catalogue.select_product)

  - `POST /ice/product`
    - Purpose: return authoritative product details for a single product id.
    - Request: `{ "session_id": "s1", "product_id": "p123" }`
    - Response (200): `{ "product_id":"p123","name":"Apples","price":1000,"currency":"ZMW","available":true }`
    - Notes: handler uses this for cache hydration only; authoritative pricing still comes from `POST /ice/cart/price`.

  Example cURL:

  ```bash
  curl -s -X POST \
    -H "Content-Type: application/json" \
    -H "X-Session-Id: s1" \
    -d '{"session_id":"s1","product_id":"p123"}' \
    "https://ice.internal/ice/product"
  ```

---

## Audit / Observability notes for ICE interactions

- When handlers call ICE, include headers: `X-Session-Id`, `X-Event-Id`, and `X-Bot-Id` where applicable.
- ICE responses that are persisted into Redis should include a `version` or `fetched_at` timestamp to support cache TTL decisions.

---

If you want, I can also add small example request/response cURL snippets for the suggested endpoints or generate OpenAPI specs for the minimal ICE endpoints above.

---

## Example cURL request / response snippets

These are small examples to share with ICE implementers. Replace `https://ice.internal` with the real ICE base URL.

- Catalog search (query)

Request:

```bash
curl -s -H "X-Session-Id: s1" -H "X-Event-Id: e1" \
  "https://ice.internal/ice/catalog?query=apples&limit=5"
```

Successful response (200):

```json
[
  {"product_id":"p123","name":"Apples","canonical_name":"Apples","primary_price":{"amount":1000,"currency":"ZMW"},"available":true},
  {"product_id":"p124","name":"Green Apples","primary_price":{"amount":1100,"currency":"ZMW"},"available":true}
]
```

- Product details

Request:

```bash
curl -s -H "X-Session-Id: s1" -H "X-Event-Id: e1" \
  "https://ice.internal/ice/product/p123"
```

Successful response (200):

```json
{
  "product_id": "p123",
  "name": "Apples",
  "description": "Fresh apples",
  "price": 1000,
  "currency": "ZMW",
  "available": true,
  "attributes": {"unit":"kg"}
}
```

- Authoritative cart pricing

Request:

```bash
curl -s -X POST -H "Content-Type: application/json" -H "X-Session-Id: s1" -H "X-Event-Id: e1" \
  -d '{"session_id":"s1","oob_ref":"oob:s1"}' \
  "https://ice.internal/ice/cart/price"
```

Successful response (200):

```json
{
  "subtotal": 1200,
  "tax": 120,
  "discount": 0,
  "grand_total": 1320,
  "lines": [
    {"product_id":"p123","unit_price":600,"quantity":2,"line_total":1200}
  ]
}
```

Notes:
- ICE should return standard HTTP status codes (200/400/404/500). Include an error body with `{ "error":"message" }` for non-200 responses.
- When ICE returns blobs that will be cached in Redis, include a `fetched_at` ISO timestamp in the response or in accompanying metadata so consumers can apply TTL/refresh logic.

