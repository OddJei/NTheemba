# Affiliate JSONB Examples (Tracking + Performance)

This file contains **affiliate-centric JSONB examples**.

Important rules:
- **Affiliate Engine (backend) is the source of truth** for affiliate logic and payouts.
- Redis is a **cache**, not truth.
- **Bot layer does tracking, not affiliate math**:
  - Bots capture affiliate codes in sessions/orders and emit simple tracking events.
  - Affiliate Engine computes earnings, tiers, multipliers, and pool allocations.
- **Bots never call affiliate-engine directly.** Bots call **ICE**, and ICE calls affiliate-engine.

---

## 1) Affiliate Profile JSONB (who the affiliate is)

```json
{
  "schema_version": "v1",
  "affiliate_id": "aff_123",
  "name": "Mary Affiliate",
  "phone": "+26097...",
  "status": "active",
  "created_at": "2026-01-21T10:16:00Z",
  "updated_at": "2026-01-21T10:16:00Z"
}
```

---

## 2) Affiliate Link JSONB (the code people use)

This matches the soft-launch affiliate engine concept of a link `code`.

```json
{
  "schema_version": "v1",
  "link_id": "link_1",
  "affiliate_id": "aff_123",
  "code": "aff-code-123",
  "campaign": "jan-promo",
  "product_id": "prd_1",
  "business_id": "biz_789",
  "created_at": "2026-01-21T10:16:00Z"
}
```

Notes:
- The bot usually only sees `code` (like `aff-code-123`).
- The bot should not guess affiliate_id if it doesn’t have it.

---

## 3) Affiliate Session Context JSONB (what the bot remembers)

Purpose: keep the affiliate attribution info attached to a session so it reaches order creation.

```json
{
  "schema_version": "v1",
  "session_id": "sess_+27..._bot_123_1737450000",
  "affiliate": {
    "affiliate_code": "aff-code-123",
    "source": "link",
    "campaign": "jan-promo",
    "first_seen_at": "2026-01-21T10:00:00Z",
    "last_seen_at": "2026-01-21T10:15:00Z"
  },
  "updated_at": "2026-01-21T10:16:00Z"
}
```

Notes:
- This is small and safe.
- Keep it in Redis so every downstream step can include `affiliate_code`.

---

## 4) Affiliate Tracking Event JSONB (what bots can emit via ICE)

The affiliate engine derives performance from an **append-only event log**.
Soft-launch conventions include these event types:
- `campaign_click` (someone clicked/entered via affiliate link)
- `conversion` (an order got attributed)
- `sale` (a payment success created commission)

Bots should mainly emit `campaign_click` (if the bot is the first system to see the affiliate code).
Order/Payment services emit `order_created` and `payment_success` in soft-launch.

```json
{
  "schema_version": "v1",
  "event_id": "evt_9d6b...",
  "event_type": "campaign_click",
  "occurred_at": "2026-01-21T10:00:05Z",
  "source": "bot-layer",
  "correlation_id": "corr_123",
  "session_id": "sess_...",
  "buyer_phone": "+260971000000",
  "business_id": "biz_789",
  "affiliate_code": "aff-code-123",
  "meta": {
    "platform": "whatsapp",
    "bot_id": "bot_123"
  }
}
```

---

## 5) Order Attribution JSONB (linking an order to an affiliate)

This is typically created in backend when an order is created.
Bots help by ensuring `affiliate_code` is present in order metadata.

```json
{
  "schema_version": "v1",
  "order_id": "ord_1",
  "business_id": "biz_789",
  "affiliate_code": "aff-code-123",
  "session_id": "sess_...",
  "user_phone": "+260971000000",
  "status": "attributed",
  "created_at": "2026-01-21T10:20:00Z"
}
```

---

## 6) Earning Record JSONB (commission per paid order)

Produced by backend logic (payment-revenue + affiliate engine).
Bots do not compute this.

```json
{
  "schema_version": "v1",
  "earning_id": "earn_1",
  "affiliate_id": "aff_123",
  "affiliate_code": "aff-code-123",
  "order_id": "ord_1",
  "payment_id": "pay_1",
  "amount": 12.50,
  "currency": "ZMW",
  "status": "pending",
  "created_at": "2026-01-21T10:25:00Z"
}
```

---

## 7) Affiliate Performance Summary JSONB (what to show on dashboards)

This mirrors the soft-launch affiliate engine metrics model:
- clicks (unique clickers)
- attributions (orders attributed)
- paid_attributions (paid orders)
- sales_volume (commission amount)
- conversion_quality = paid_attributions / clicks (only after min clicks)

```json
{
  "schema_version": "v1",
  "affiliate_id": "aff_123",
  "window": {
    "from": "2026-01-01T00:00:00Z",
    "to": "2026-01-21T23:59:59Z"
  },
  "metrics": {
    "clicks": 120,
    "attributions": 20,
    "paid_attributions": 12,
    "sales_volume_zmw": 320.0,
    "unique_buyers": 11,
    "msme_referrals": 2,
    "conversion_quality": 0.10
  },
  "tier": {
    "name": "silver",
    "multiplier": 1.5
  },
  "updated_at": "2026-01-21T10:30:00Z"
}
```

Notes:
- This summary should come from affiliate-engine (via ICE).
- You can cache it in Redis for quick display.

---

## Recommended Redis keys + TTLs (affiliate-centric)

| Key pattern | Stores | Suggested TTL | Notes |
+|---|---|---:|---|
| `affiliate:profile:{affiliate_id}` | Affiliate profile | 6–24h | Rare changes |
| `affiliate:link:{affiliate_code}` | Link metadata | 1–24h | Small object |
| `affiliate:ctx:{session_id}` | Affiliate info for this session | 1–24h | Keep until checkout ends |
| `affiliate:perf:{affiliate_id}:{yyyy_mm_dd}` | Cached daily/rolling summary | 5–60m | Cache only; not truth |
| `affiliate:events:last:{affiliate_id}` | Last emitted event id/time | 5–60m | Helps debugging |

---

## What bots MUST do vs MUST NOT do

Bots MUST:
- capture `affiliate_code` from inbound metadata when present
- store it in session context and/or OOB meta
- ensure `affiliate_code` is included in order creation metadata (through ICE)
- optionally emit `campaign_click` tracking via ICE (best effort)

Bots MUST NOT:
- calculate commission amounts
- decide tier/multiplier
- compute pool payouts
- call affiliate-engine directly
