# Bot Service JSONB Examples

This file contains example JSONB payloads and short notes for `bot`, `owner`, and `catalog` blobs. Each blob should be versioned (`schema_version`) and persisted in Postgres JSONB, cached in Redis with a TTL, and kept bounded in size.

---

## 1) Bot JSONB (control plane + lightweight live stats)

```json
{
  "schema_version": "v1",
  "bot_id": "bot_123",
  "owner_id": "own_456",
  "business_id": "biz_789",
  "bot_type": "custom",
  "status": {
    "active": true,
    "disabled_reason": null,
    "channels": ["whatsapp", "http"]
  },
  "routing": {
    "primary_lane": "bot:lane:custom",
    "default_mode": "public"
  },
  "stats": {
    "active_sessions_5m": 42,
    "active_users_5m": 39,
    "last_seen_at": "2026-01-21T10:15:00Z"
  },
  "updated_at": "2026-01-21T10:16:00Z"
}
```

Notes:
- Keep `stats` small and approximate; consider storing rapidly-changing counters separately to avoid frequent JSONB rewrites.
- Redis TTL suggestion: 5–30 minutes (cache-backed, Postgres is source of truth).

---

## 2) Owner JSONB (owner + business profile)

```json
{
  "schema_version": "v1",
  "owner_id": "own_456",
  "owner": {
    "name": "Jane Doe",
    "phone": "+27...",
    "email": "jane@example.com"
  },
  "business": {
    "business_id": "biz_789",
    "name": "Fresh Mart",
    "industry": "grocery",
    "location": {
      "country": "ZA",
      "city": "Cape Town",
      "address": "123 Main Rd",
      "geo": { "lat": -33.9, "lng": 18.4 }
    }
  },
  "preferences": {
    "currency": "ZAR",
    "locale": "en"
  },
  "updated_at": "2026-01-20T08:00:00Z"
}
```

Notes:
- Owner blobs change rarely; long Redis TTL (hours to a day) is appropriate. Invalidate on profile update.

---

## 3) Catalog JSONB (products + inventory)

**Recommended approach:** keep a small catalog index per owner and a separate product snapshot per product. Avoid storing huge product lists in a single JSONB.

Catalog index (small):
```json
{
  "schema_version": "v1",
  "business_id": "biz_789",
  "product_ids": ["prd_1", "prd_2", "prd_3"],
  "updated_at": "2026-01-21T09:00:00Z"
}
```

Product snapshot (per-product JSONB):
```json
{
  "schema_version": "v1",
  "product_id": "prd_1",
  "business_id": "biz_789",
  "name": "Maize Meal 5kg",
  "price": { "amount": 7999, "currency": "ZAR" },
  "inventory": {
    "in_stock": true,
    "remaining": 12,
    "updated_at": "2026-01-21T10:10:00Z"
  },
  "updated_at": "2026-01-21T10:10:00Z"
}
```

Notes:
- Inventory changes frequently; use per-product JSONB so updates are focused and small.
- Redis TTL suggestion: product snapshots 1–10 minutes; catalog index 30–120 minutes.
- If product counts per owner are small (<= 100), an owner-level catalog blob may be acceptable; beyond that split by product.

---

## General guidance

- Always include `schema_version` and `updated_at`.
- Enforce a maximum safe serialized size for cached JSON (e.g., 16KB–64KB); store large blobs or attachments in object storage and reference them.
- Prefer JSONB partial updates in Postgres (`jsonb_set`) and RedisJSON for atomic partial cache updates when available.
- Implement single-flight hydration locks and negative caching to avoid thundering-herd on misses.
- Track metrics: `cache_hit`, `cache_miss`, `jsonb_size`, `evicted_keys`, and `hydrate_latency`.

---

## 4) Bot Config / Feature Flags JSONB

Purpose: runtime switches and limits without redeploy.

```json
{
  "schema_version": "v1",
  "bot_id": "bot_123",
  "enabled": {
    "intent": true,
    "catalog": true,
    "payments": false,
    "handover_to_human": true
  },
  "channels": {
    "whatsapp": { "enabled": true },
    "sms": { "enabled": false },
    "http": { "enabled": true }
  },
  "limits": {
    "max_messages_per_minute": 120,
    "max_attachment_count": 5,
    "max_attachment_bytes": 2000000
  },
  "experiments": {
    "route_version": "v1",
    "reply_style": "short"
  },
  "updated_at": "2026-01-21T10:16:00Z"
}
```

Notes:
- Keep secrets out of JSONB; reference secret IDs only.
- Redis TTL suggestion: 1–6 hours (invalidate on updates).

---

## 5) Bot Routing Rules JSONB

Purpose: deterministic routing decisions (lane, intent required defaults, fallbacks).

```json
{
  "schema_version": "v1",
  "bot_id": "bot_123",
  "primary_lane": "bot:lane:custom",
  "intent_required_default": true,
  "fallbacks": {
    "on_intent_failure": "reply:clarify",
    "on_downstream_timeout": "reply:generic_error"
  },
  "rules": [
    {
      "when": { "platform": "whatsapp" },
      "then": { "intent_required": true }
    },
    {
      "when": { "session_mode": "staff" },
      "then": { "lane": "bot:lane:staff" }
    }
  ],
  "updated_at": "2026-01-21T10:16:00Z"
}
```

Notes:
- Prefer simple rule sets; complicated routing belongs in code or a rules engine.
- Redis TTL suggestion: 1–6 hours (invalidate on updates).

---

## 6) Bot Policy / Permissions JSONB

Purpose: what actions this bot is allowed to perform and safety/compliance knobs.

```json
{
  "schema_version": "v1",
  "bot_id": "bot_123",
  "allowed_actions": ["browse_catalog", "create_order", "update_order"],
  "blocked_actions": ["refund", "delete_user"],
  "safety": {
    "pii_redaction": true,
    "max_reply_length_chars": 1500,
    "allow_external_links": false
  },
  "compliance": {
    "industry": "grocery",
    "requires_opt_in": true
  },
  "updated_at": "2026-01-21T10:16:00Z"
}
```

Notes:
- Use this to gate tool calls and high-risk actions.
- Redis TTL suggestion: 1–24 hours (invalidate on updates).

---

## 7) Bot Templates / Copy Library JSONB

Purpose: reusable message templates per locale/channel.

```json
{
  "schema_version": "v1",
  "bot_id": "bot_123",
  "locale": "en",
  "templates": {
    "welcome": "Welcome to {{business_name}}. What would you like today?",
    "order_confirmed": "Thanks! Your order {{order_id}} is confirmed.",
    "out_of_stock": "Sorry, {{product_name}} is out of stock. Want an alternative?"
  },
  "updated_at": "2026-01-21T10:16:00Z"
}
```

Notes:
- Keep templates simple (string replacement). If templates get complex, split by key and version.
- Redis TTL suggestion: 6–24 hours (invalidate on updates).

---

## 8) Bot Flow / Graph Definition JSONB

Purpose: versioned conversation flow definition. Keep large flows as separate docs referenced by `flow_version`.

```json
{
  "schema_version": "v1",
  "bot_id": "bot_123",
  "flow_version": "flow_2026_01_21_01",
  "entry_node": "start",
  "nodes": [
    {
      "id": "start",
      "type": "prompt",
      "template_key": "welcome",
      "transitions": [
        { "when": { "intent": "browse_catalog" }, "to": "catalog" },
        { "when": { "intent": "create_order" }, "to": "order" }
      ]
    },
    {
      "id": "catalog",
      "type": "action",
      "action": "browse_catalog"
    },
    {
      "id": "order",
      "type": "action",
      "action": "create_order"
    }
  ],
  "updated_at": "2026-01-21T10:16:00Z"
}
```

Notes:
- For very large flows, store `nodes` as separate documents or a compiled artifact.
- Redis TTL suggestion: hours to a day (invalidate on new flow_version publish).

---

## 9) Bot Integrations Metadata JSONB (no secrets)

Purpose: track enabled integrations and their config references.

```json
{
  "schema_version": "v1",
  "bot_id": "bot_123",
  "integrations": [
    {
      "name": "payment_provider",
      "enabled": true,
      "provider": "paystack",
      "secret_ref": "secret://vault/paystack/bot_123",
      "config": { "callback_url": "https://example.com/pay/callback" }
    },
    {
      "name": "delivery_provider",
      "enabled": false,
      "provider": "internal",
      "secret_ref": null,
      "config": {}
    }
  ],
  "updated_at": "2026-01-21T10:16:00Z"
}
```

Notes:
- Store secrets in a secret manager; only keep `secret_ref` here.
- Redis TTL suggestion: 1–24 hours (invalidate on updates).

---

## 10) Bot Knowledge / Retrieval Config JSONB (pointers only)

Purpose: retrieval settings and index references (not raw documents).

```json
{
  "schema_version": "v1",
  "bot_id": "bot_123",
  "kb": {
    "index_ref": "vector://kb/biz_789",
    "namespace": "products",
    "top_k": 5,
    "min_score": 0.25,
    "filters": { "business_id": "biz_789" }
  },
  "updated_at": "2026-01-21T10:16:00Z"
}
```

Notes:
- Keep this stable; changes should be versioned and rolled out carefully.
- Redis TTL suggestion: 1–24 hours (invalidate on updates).

---

## 11) Bot Health / Ops Snapshot JSONB (optional)

Purpose: lightweight operational snapshot for dashboards and degraded-mode routing.

```json
{
  "schema_version": "v1",
  "bot_id": "bot_123",
  "health": {
    "status": "healthy",
    "degraded": false,
    "last_error": null,
    "last_ok_at": "2026-01-21T10:15:55Z"
  },
  "providers": {
    "whatsapp": { "status": "healthy", "last_latency_ms": 220 },
    "ice": { "status": "healthy", "last_latency_ms": 80 }
  },
  "rate_limits": {
    "blocked": false,
    "reason": null
  },
  "updated_at": "2026-01-21T10:16:00Z"
}
```

Notes:
- This should be TTL’d (very short) and never treated as source-of-truth.
- Redis TTL suggestion: 30 seconds – 5 minutes.

---

## Recommended Redis keys + TTLs (bot-centric)

These are suggested key patterns for caching the JSONB blobs above.

Guidelines:
- **Postgres is source-of-truth** for JSONB objects.
- Redis entries are **cache copies** with TTLs; update/invalidate on DB changes.
- Keep values **bounded** (avoid storing huge catalogs in one key).
- Use **single-flight locks** for cache misses that call ICE or other services.

| Key pattern | Stores | Suggested TTL | Update / invalidation trigger | Notes |
|---|---|---:|---|---|
| `bot:core:{bot_id}` | Bot JSONB (control plane + small stats) | 5–30m | bot update, bot activity heartbeat | Keep stats lightweight; consider moving hot counters to a separate key. |
| `bot:owner:{owner_id}` | Owner JSONB | 6–24h | owner/business profile update | Rare changes; long TTL is safe if you invalidate on updates. |
| `bot:catalog:index:{business_id}` | Catalog index JSONB | 30–120m | product create/update/delete | Keep only `product_ids` and minimal metadata. |
| `bot:catalog:product:{product_id}` | Product snapshot JSONB | 1–10m | inventory/price update | Inventory is hot; keep per-product updates small. |
| `bot:config:{bot_id}` | Bot config / feature flags JSONB | 1–6h | config publish | Never store secrets; only references (`secret_ref`). |
| `bot:routing:{bot_id}` | Bot routing rules JSONB | 1–6h | routing rules publish | Keep rules simple and deterministic. |
| `bot:policy:{bot_id}` | Bot policy/permissions JSONB | 6–24h | policy update | Gate tool calls/actions using this. |
| `bot:templates:{bot_id}:{locale}` | Bot templates JSONB | 6–24h | template update | If templates grow large, split by template key. |
| `bot:flow:{bot_id}:{flow_version}` | Flow definition JSONB | 6–24h | new flow_version publish | Prefer immutable flow versions; keep `flow_version` stable. |
| `bot:integrations:{bot_id}` | Integrations metadata JSONB | 1–24h | integration toggle/update | Keep only metadata + secret refs. |
| `bot:kb:{bot_id}` | Knowledge/retrieval config JSONB | 1–24h | KB config update | Points to indexes/namespaces; not the docs themselves. |
| `bot:health:{bot_id}` | Health/ops snapshot JSONB | 30s–5m | heartbeat/health checks | Treat as ephemeral; safe to expire quickly. |
| `lock:hydrate:{session_id}` | Single-flight hydration lock (string) | 10–30s | set on cache miss | Prevents thundering herd when calling ICE. |
| `neg:hydrate:{session_id}` | Negative cache (string/json) | 10–60s | set on hydrate failure | Avoid repeated ICE hits during outages. |

Notes:
- If you use Redis Streams heavily, consider **separating** streams from KV/cache Redis to avoid contention.
- Use an eviction policy appropriate for caching (e.g., `allkeys-lru` or `volatile-lru`) and set `maxmemory`.

Path: `bot-ingress-service/docs/bot_jsonb_examples.md`
