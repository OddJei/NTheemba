# Customer (User) JSONB Examples

This file contains customer/user-centric JSONB examples. These objects are **user-owned** (customer-centric) and can be persisted in Postgres JSONB and cached in Redis with TTLs.

Guidelines:
- **Postgres is source-of-truth**.
- Redis is a **cache**, not truth; choose TTLs per update frequency.
- Keep values **bounded** (avoid giant transcripts or full catalogs in user blobs).
- Store sensitive data carefully (PII, auth tokens, payment data). Prefer **references** to secret managers or token vaults.

---

## 1) Customer Profile JSONB (stable identity + contact)

```json
{
  "schema_version": "v1",
  "user_id": "usr_123",
  "phone": "+27...",
  "name": "John Customer",
  "locale": "en",
  "timezone": "Africa/Johannesburg",
  "status": {
    "active": true,
    "banned": false,
    "reason": null
  },
  "updated_at": "2026-01-21T10:16:00Z"
}
```

Notes:
- This changes rarely; longer TTL is fine.

---

## 2) Customer Auth / Roles JSONB (per business scope)

```json
{
  "schema_version": "v1",
  "user_id": "usr_123",
  "business_id": "biz_789",
  "authenticated": true,
  "roles": ["customer"],
  "permissions": ["place_order"],
  "updated_at": "2026-01-21T10:16:00Z"
}
```

Notes:
- Keep it minimal; do not cache raw JWTs here.

---

## 3) User Preferences JSONB

```json
{
  "schema_version": "v1",
  "user_id": "usr_123",
  "preferences": {
    "language": "en",
    "currency": "ZAR",
    "delivery_notes": "Call when outside",
    "marketing_opt_in": false
  },
  "updated_at": "2026-01-21T10:16:00Z"
}
```

---

## 4) Address Book JSONB

```json
{
  "schema_version": "v1",
  "user_id": "usr_123",
  "addresses": [
    {
      "address_id": "addr_1",
      "label": "Home",
      "line1": "123 Main Rd",
      "city": "Cape Town",
      "country": "ZA",
      "postal_code": "8001",
      "geo": { "lat": -33.9, "lng": 18.4 },
      "is_default": true
    }
  ],
  "updated_at": "2026-01-21T10:16:00Z"
}
```

Notes:
- Addresses are PII; consider redaction in logs and strict access control.

---

## 5) Customer–Bot Relationship JSONB (user’s view of a bot)

Purpose: user-specific settings for a specific bot (mute, last interaction, default preferences).

```json
{
  "schema_version": "v1",
  "user_id": "usr_123",
  "bot_id": "bot_123",
  "business_id": "biz_789",
  "relationship": {
    "muted": false,
    "blocked": false,
    "tags": ["repeat_customer"]
  },
  "last_interaction_at": "2026-01-21T10:15:00Z",
  "updated_at": "2026-01-21T10:16:00Z"
}
```

---

## 6) User–Bot Session Snapshot JSONB (session-scoped)

Purpose: a compact snapshot of the current session state for a user with a bot.

```json
{
  "schema_version": "v1",
  "session_id": "sess_+27..._bot_123_1737450000",
  "user_id": "usr_123",
  "bot_id": "bot_123",
  "platform": "whatsapp",
  "mode": "customer",
  "state": {
    "current_node": "catalog",
    "last_intent": "browse_catalog",
    "reset_requested": false
  },
  "started_at": "2026-01-21T10:00:00Z",
  "last_active_at": "2026-01-21T10:15:00Z",
  "updated_at": "2026-01-21T10:16:00Z"
}
```

Notes:
- Keep this small; the larger ICE hydrate blob should be separate (see next section).

---

## 7) Session Context (ICE Hydrate) JSONB (user-centric view)

Purpose: hydrated context used by downstream services. Keep it versioned and bounded.

```json
{
  "schema_version": "v1",
  "session_id": "sess_+27..._bot_123_1737450000",
  "source": "ice",
  "last_hydrated_at": "2026-01-21T10:15:30Z",
  "intent_required": true,
  "session_state": {
    "cart_id": "cart_1",
    "last_seen_product_id": "prd_1"
  },
  "order_draft": {
    "order_id": "ord_draft_1",
    "currency": "ZAR",
    "items": [
      { "product_id": "prd_1", "qty": 1, "unit_price": 7999 }
    ],
    "totals": { "subtotal": 7999, "delivery": 0, "tax": 0, "grand_total": 7999 }
  },
  "bot_meta": {
    "business_id": "biz_789"
  },
  "updated_at": "2026-01-21T10:16:00Z"
}
```

Notes:
- Avoid storing full chat transcripts here.
- Consider compressing or splitting large subtrees.

---

## 8) Cart JSONB (user shopping cart, not yet an order)

```json
{
  "schema_version": "v1",
  "cart_id": "cart_1",
  "user_id": "usr_123",
  "business_id": "biz_789",
  "items": [
    {
      "product_id": "prd_1",
      "qty": 1,
      "price_snapshot": { "amount": 7999, "currency": "ZAR" }
    }
  ],
  "updated_at": "2026-01-21T10:16:00Z"
}
```

---

## 9) Order Draft JSONB (pre-checkout)

```json
{
  "schema_version": "v1",
  "order_id": "ord_draft_1",
  "user_id": "usr_123",
  "business_id": "biz_789",
  "status": "draft",
  "items": [
    { "product_id": "prd_1", "qty": 1, "unit_price": 7999 }
  ],
  "delivery": {
    "address_id": "addr_1",
    "method": "standard"
  },
  "payment": {
    "method": "cash_on_delivery",
    "payment_ref": null
  },
  "totals": { "subtotal": 7999, "delivery": 0, "tax": 0, "grand_total": 7999 },
  "updated_at": "2026-01-21T10:16:00Z"
}
```

---

## 10) Notification Preferences JSONB

```json
{
  "schema_version": "v1",
  "user_id": "usr_123",
  "channels": {
    "whatsapp": { "enabled": true },
    "sms": { "enabled": false },
    "email": { "enabled": false }
  },
  "quiet_hours": { "start": "21:00", "end": "07:00" },
  "updated_at": "2026-01-21T10:16:00Z"
}
```

---

## 11) Consent / Compliance JSONB

```json
{
  "schema_version": "v1",
  "user_id": "usr_123",
  "consents": {
    "terms_accepted": { "accepted": true, "accepted_at": "2026-01-01T10:00:00Z" },
    "marketing": { "accepted": false, "accepted_at": null }
  },
  "updated_at": "2026-01-21T10:16:00Z"
}
```

---

## Recommended Redis keys + TTLs (customer-centric)

| Key pattern | Stores | Suggested TTL | Notes |
+|---|---|---:|---|
| `user:profile:{user_id}` | Customer profile | 6–24h | Invalidate on profile change |
| `user:auth:{user_id}:{business_id}` | Roles/auth context | 5–30m | Avoid caching raw tokens |
| `user:prefs:{user_id}` | Preferences | 6–24h | Invalidate on update |
| `user:addresses:{user_id}` | Address book | 6–24h | PII; restrict access |
| `user:bot:{user_id}:{bot_id}` | Customer–bot relationship | 1–24h | Small object |
| `session:snapshot:{session_id}` | Session snapshot | 5–30m | Hot key; keep small |
| `session:ctx:{session_id}` | ICE hydrate session context | 10–30m | Bounded, versioned |
| `cart:{cart_id}` | Cart | 5–30m | Update frequently |
| `order:draft:{order_id}` | Order draft | 10–60m | Invalidate on checkout |
| `user:notify:{user_id}` | Notification prefs | 6–24h | Rare changes |
| `user:consent:{user_id}` | Consent/compliance | 6–24h | Rare changes |
| `lock:hydrate:{session_id}` | Single-flight lock | 10–30s | Avoid thundering herd |
| `neg:hydrate:{session_id}` | Negative cache | 10–60s | Avoid hammering ICE |

---

Path: `bot-ingress-service/docs/customer_jsonb_examples.md`
