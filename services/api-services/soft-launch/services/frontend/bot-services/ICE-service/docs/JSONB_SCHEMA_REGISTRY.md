# ICE Service - Consolidated JSONB Schema Registry

Complete mapping of all JSONB blob types to adapters, fields, and relationships.

---

## Schema Registry Overview

Each blob has:
- **Name & Purpose**: what it stores and why
- **Schema Version**: current version (for migrations)
- **Adapter Dependencies**: which adapters populate which fields
- **Fields**: complete field list with types, required flag, and source adapter
- **Redis TTL**: suggested cache lifetime
- **Postgres Table**: where it's stored

---

## 1. BOT CORE BLOB

**Purpose:** Control plane data + lightweight live stats for a bot

**Schema Version:** v1

**Postgres Table:** `ice_bot_core`

**Redis TTL:** 5–30 minutes

**Adapter Dependencies:**
- Bot-session adapter (health, stats, last_seen_at)

### Fields

| Field | Type | Required | Source | Notes |
|-------|------|----------|--------|-------|
| `schema_version` | string | ✓ | Manual | "v1" |
| `bot_id` | string | ✓ | Manual | Unique bot identifier |
| `owner_id` | string | ✓ | Manual | Bot owner (MSME) |
| `business_id` | string | ✓ | MSME adapter | From business profile |
| `bot_type` | string | ✓ | Manual | "custom", "default", etc. |
| `status.active` | boolean | ✓ | Manual | Is bot enabled |
| `status.disabled_reason` | string | ✗ | Manual | Reason if disabled |
| `status.channels` | array | ✓ | Manual | ["whatsapp", "http"] |
| `routing.primary_lane` | string | ✓ | Manual | Default routing lane |
| `routing.default_mode` | string | ✓ | Manual | "public", "staff", etc. |
| `stats.active_sessions_5m` | int | ✗ | Bot-session adapter | Approx sessions in 5m |
| `stats.active_users_5m` | int | ✗ | Bot-session adapter | Approx unique users in 5m |
| `stats.last_seen_at` | ISO8601 | ✗ | Bot-session adapter | Last activity timestamp |
| `updated_at` | ISO8601 | ✓ | Manual | Record update time |

---

## 2. OWNER + BUSINESS PROFILE BLOB

**Purpose:** Owner identity + business profile (MSME context)

**Schema Version:** v1

**Postgres Table:** `ice_owner_profile`

**Redis TTL:** 6–24 hours

**Adapter Dependencies:**
- MSME adapter (all business fields)
- Auth adapter (owner verification)

### Fields

| Field | Type | Required | Source | Notes |
|-------|------|----------|--------|-------|
| `schema_version` | string | ✓ | Manual | "v1" |
| `owner_id` | string | ✓ | Manual | Unique owner ID |
| `owner.name` | string | ✓ | MSME adapter | Owner full name |
| `owner.phone` | string | ✓ | MSME adapter | Owner phone |
| `owner.email` | string | ✓ | MSME adapter | Owner email |
| `business.business_id` | string | ✓ | MSME adapter | Business/MSME ID |
| `business.name` | string | ✓ | MSME adapter | Business name |
| `business.industry` | string | ✗ | MSME adapter | "grocery", "retail", etc. |
| `business.location.country` | string | ✗ | MSME adapter | Country code (e.g., "ZA") |
| `business.location.city` | string | ✗ | MSME adapter | City name |
| `business.location.address` | string | ✗ | MSME adapter | Street address |
| `business.location.geo.lat` | float | ✗ | MSME adapter | Latitude |
| `business.location.geo.lng` | float | ✗ | MSME adapter | Longitude |
| `preferences.currency` | string | ✓ | MSME adapter | "ZAR", "ZMW", etc. |
| `preferences.locale` | string | ✓ | MSME adapter | "en", "zu", etc. |
| `updated_at` | ISO8601 | ✓ | Manual | Record update time |

---

## 3. CATALOG INDEX BLOB

**Purpose:** Product list for a business (small index, not full catalog)

**Schema Version:** v1

**Postgres Table:** `ice_catalog_index`

**Redis TTL:** 30–120 minutes

**Adapter Dependencies:**
- Catalog adapter (product_ids, product count)

### Fields

| Field | Type | Required | Source | Notes |
|-------|------|----------|--------|-------|
| `schema_version` | string | ✓ | Manual | "v1" |
| `business_id` | string | ✓ | Catalog adapter | Business/MSME ID |
| `product_ids` | array | ✓ | Catalog adapter | List of product IDs |
| `product_count` | int | ✓ | Catalog adapter | Total product count |
| `variant_count` | int | ✓ | Catalog adapter | Total variant count |
| `updated_at` | ISO8601 | ✓ | Manual | Last sync time |

---

## 4. PRODUCT SNAPSHOT BLOB

**Purpose:** Individual product snapshot with inventory availability

**Schema Version:** v1

**Postgres Table:** `ice_product_snapshot`

**Redis TTL:** 1–10 minutes

**Adapter Dependencies:**
- Catalog adapter (product metadata, variants, inventory)

### Fields

| Field | Type | Required | Source | Notes |
|-------|------|----------|--------|-------|
| `schema_version` | string | ✓ | Manual | "v1" |
| `product_id` | string | ✓ | Catalog adapter | Unique product ID |
| `business_id` | string | ✓ | Catalog adapter | Business/MSME ID |
| `name` | string | ✓ | Catalog adapter | Product name |
| `description` | string | ✗ | Catalog adapter | Product description |
| `price.amount` | int | ✓ | Catalog adapter | Price in minor units |
| `price.currency` | string | ✓ | Catalog adapter | "ZAR", "ZMW", etc. |
| `is_active` | boolean | ✓ | Catalog adapter | Product available |
| `media_urls` | array | ✗ | Catalog adapter | Image URLs from Nextcloud |
| `variants` | array | ✓ | Catalog adapter | Array of variant objects |
| `variants[].variant_id` | string | ✓ | Catalog adapter | SKU identifier |
| `variants[].name` | string | ✓ | Catalog adapter | Variant name (e.g., "16GB RAM") |
| `variants[].sku` | string | ✓ | Catalog adapter | SKU code |
| `variants[].price_override` | int | ✗ | Catalog adapter | Variant-specific price |
| `inventory[].variant_id` | string | ✓ | Catalog adapter | Variant ID |
| `inventory[].stock_level` | int | ✓ | Catalog adapter | Total stock |
| `inventory[].reserved` | int | ✓ | Catalog adapter | Reserved/allocated stock |
| `inventory[].available` | int | ✓ | Catalog adapter | stock_level - reserved |
| `inventory[].in_stock` | boolean | ✓ | Catalog adapter | available > 0 |
| `inventory[].updated_at` | ISO8601 | ✓ | Catalog adapter | Last inventory sync |
| `updated_at` | ISO8601 | ✓ | Manual | Record update time |

---

## 5. SESSION SNAPSHOT BLOB

**Purpose:** User's current session state with a bot

**Schema Version:** v1

**Postgres Table:** `ice_session_snapshot`

**Redis TTL:** 5–30 minutes

**Adapter Dependencies:**
- Bot-session adapter (session creation, state retrieval)
- User-bot-session adapter (session context)

### Fields

| Field | Type | Required | Source | Notes |
|-------|------|----------|--------|-------|
| `schema_version` | string | ✓ | Manual | "v1" |
| `session_id` | string | ✓ | Bot-session adapter | Unique session ID |
| `user_id` | string | ✓ | Bot-session adapter | Customer/user ID |
| `bot_id` | string | ✓ | Bot-session adapter | Bot ID |
| `business_id` | string | ✓ | MSME adapter | Business/MSME ID |
| `phone` | string | ✓ | Bot-session adapter | User phone |
| `platform` | string | ✓ | Bot-session adapter | "whatsapp", "sms", "http" |
| `mode` | string | ✓ | Bot-session adapter | "customer", "staff", etc. |
| `state.current_node` | string | ✗ | Bot-session adapter | Current flow node |
| `state.last_intent` | string | ✗ | Bot-session adapter | Last parsed intent |
| `state.reset_requested` | boolean | ✗ | Bot-session adapter | Reset session flag |
| `started_at` | ISO8601 | ✓ | Bot-session adapter | Session start time |
| `last_active_at` | ISO8601 | ✓ | Bot-session adapter | Last activity time |
| `updated_at` | ISO8601 | ✓ | Manual | Record update time |

---

## 6. HYDRATED SESSION CONTEXT BLOB (ICE BLOB)

**Purpose:** Complete hydrated context for a session (from all adapters)

**Schema Version:** v1

**Postgres Table:** `ice_hydrated_session`

**Redis TTL:** 10–30 minutes

**Adapter Dependencies:**
- Bot-session adapter (session state, cart_id)
- MSME adapter (user profile, business policies)
- Catalog adapter (product snapshots, inventory)
- Cart-order adapter (order draft)
- Affiliate adapter (affiliate context)

### Fields

| Field | Type | Required | Source | Notes |
|-------|------|----------|--------|-------|
| `schema_version` | string | ✓ | Manual | "v1" |
| `session_id` | string | ✓ | Bot-session adapter | Session ID |
| `user_id` | string | ✓ | Bot-session adapter | User ID |
| `business_id` | string | ✓ | MSME adapter | Business ID |
| `source` | string | ✓ | Manual | "ice" (hydration source) |
| `last_hydrated_at` | ISO8601 | ✓ | Manual | Last hydration time |
| `intent_required` | boolean | ✓ | Manual | NLU intent required |
| `session_state.cart_id` | string | ✗ | Cart-order adapter | Current cart ID |
| `session_state.last_seen_product_id` | string | ✗ | Catalog adapter | Last viewed product |
| `user.profile.name` | string | ✓ | Bot-session adapter | User name |
| `user.profile.phone` | string | ✓ | Bot-session adapter | User phone |
| `user.preferences.language` | string | ✗ | MSME adapter | "en", "zu", etc. |
| `user.preferences.currency` | string | ✗ | MSME adapter | "ZAR", "ZMW" |
| `business.name` | string | ✓ | MSME adapter | Business name |
| `business.industry` | string | ✗ | MSME adapter | Industry category |
| `business.policies.plan` | string | ✓ | MSME adapter | Subscription plan |
| `business.policies.features` | object | ✗ | MSME adapter | Feature flags |
| `business.policies.limits` | object | ✗ | MSME adapter | Rate limits, quotas |
| `catalog.product_ids` | array | ✗ | Catalog adapter | Available products |
| `catalog.product_count` | int | ✗ | Catalog adapter | Total products |
| `order_draft.order_id` | string | ✗ | Cart-order adapter | Current order draft ID |
| `order_draft.items` | array | ✗ | Cart-order adapter | Order line items |
| `order_draft.items[].product_id` | string | ✗ | Catalog adapter | Product ID |
| `order_draft.items[].qty` | int | ✗ | Cart-order adapter | Quantity |
| `order_draft.items[].unit_price` | int | ✗ | Catalog adapter | Price in minor units |
| `order_draft.totals.subtotal` | int | ✗ | Cart-order adapter | Subtotal |
| `order_draft.totals.delivery` | int | ✗ | Delivery adapter | Delivery fee |
| `order_draft.totals.tax` | int | ✗ | Manual | Tax amount |
| `order_draft.totals.grand_total` | int | ✗ | Cart-order adapter | Final total |
| `affiliate.code` | string | ✗ | Affiliate adapter | Affiliate code |
| `affiliate.campaign` | string | ✗ | Affiliate adapter | Campaign name |
| `affiliate.first_seen_at` | ISO8601 | ✗ | Affiliate adapter | When code first used |
| `bot_meta.bot_id` | string | ✓ | Bot-session adapter | Bot ID |
| `bot_meta.platform` | string | ✓ | Bot-session adapter | "whatsapp", etc. |
| `updated_at` | ISO8601 | ✓ | Manual | Record update time |

---

## 7. CART BLOB

**Purpose:** User's shopping cart (pre-checkout)

**Schema Version:** v1

**Postgres Table:** `ice_cart`

**Redis TTL:** 5–30 minutes

**Adapter Dependencies:**
- Cart-order adapter (cart creation, items, totals)
- Catalog adapter (price snapshots per item)

### Fields

| Field | Type | Required | Source | Notes |
|-------|------|----------|--------|-------|
| `schema_version` | string | ✓ | Manual | "v1" |
| `cart_id` | string | ✓ | Cart-order adapter | Unique cart ID |
| `user_id` | string | ✓ | Manual | User ID |
| `business_id` | string | ✓ | Manual | Business ID |
| `items` | array | ✓ | Cart-order adapter | Array of items |
| `items[].product_id` | string | ✓ | Catalog adapter | Product ID |
| `items[].qty` | int | ✓ | Cart-order adapter | Quantity |
| `items[].price_snapshot.amount` | int | ✓ | Catalog adapter | Unit price in minor units |
| `items[].price_snapshot.currency` | string | ✓ | Catalog adapter | Currency code |
| `subtotal` | int | ✓ | Cart-order adapter | Subtotal before tax/delivery |
| `updated_at` | ISO8601 | ✓ | Manual | Last update time |

---

## 8. ORDER DRAFT BLOB

**Purpose:** Pre-checkout order state (before payment)

**Schema Version:** v1

**Postgres Table:** `ice_order_draft`

**Redis TTL:** 10–60 minutes

**Adapter Dependencies:**
- Cart-order adapter (order creation, items, totals)
- Delivery adapter (delivery address, method)
- Payment adapter (payment method reference)
- Catalog adapter (price snapshots)

### Fields

| Field | Type | Required | Source | Notes |
|-------|------|----------|--------|-------|
| `schema_version` | string | ✓ | Manual | "v1" |
| `order_id` | string | ✓ | Cart-order adapter | Order ID (draft) |
| `user_id` | string | ✓ | Manual | User ID |
| `business_id` | string | ✓ | Manual | Business ID |
| `status` | string | ✓ | Cart-order adapter | "draft", "pending", etc. |
| `items` | array | ✓ | Cart-order adapter | Line items |
| `items[].product_id` | string | ✓ | Catalog adapter | Product ID |
| `items[].qty` | int | ✓ | Cart-order adapter | Quantity |
| `items[].unit_price` | int | ✓ | Catalog adapter | Unit price in minor units |
| `delivery.address_id` | string | ✗ | Delivery adapter | Delivery address ID |
| `delivery.address_line` | string | ✗ | Delivery adapter | Full address |
| `delivery.method` | string | ✗ | Delivery adapter | "standard", "express", etc. |
| `delivery.location_metadata` | object | ✗ | Delivery adapter | Pickup/delivery location info |
| `payment.method` | string | ✗ | Payment adapter | "card", "mobile_money", "cod" |
| `payment.payment_ref` | string | ✗ | Payment adapter | External payment ID (if initiated) |
| `payment.phone_number` | string | ✗ | Payment adapter | Payer phone (normalized) |
| `totals.subtotal` | int | ✓ | Cart-order adapter | Subtotal |
| `totals.delivery` | int | ✓ | Delivery adapter | Delivery fee |
| `totals.tax` | int | ✗ | Manual | Tax amount |
| `totals.grand_total` | int | ✓ | Cart-order adapter | Final total |
| `updated_at` | ISO8601 | ✓ | Manual | Record update time |

---

## 9. ORDER CONFIRMATION BLOB

**Purpose:** Confirmed order snapshot (after checkout, pre-payment)

**Schema Version:** v1

**Postgres Table:** `ice_order_confirmed`

**Redis TTL:** 30–120 minutes

**Adapter Dependencies:**
- Cart-order adapter (order confirmation, items, status)
- Order-delivery adapter (order metadata)
- Payment adapter (payment initiation response)

### Fields

| Field | Type | Required | Source | Notes |
|-------|------|----------|--------|-------|
| `schema_version` | string | ✓ | Manual | "v1" |
| `order_id` | string | ✓ | Cart-order adapter | Confirmed order ID |
| `user_id` | string | ✓ | Manual | User ID |
| `business_id` | string | ✓ | Manual | Business ID |
| `status` | string | ✓ | Cart-order adapter | "CONFIRMED", "PENDING_PAYMENT" |
| `items` | array | ✓ | Cart-order adapter | Confirmed items |
| `items[].product_id` | string | ✓ | Catalog adapter | Product ID |
| `items[].qty` | int | ✓ | Cart-order adapter | Quantity |
| `items[].unit_price` | int | ✓ | Catalog adapter | Locked price |
| `delivery.method` | string | ✓ | Order-delivery adapter | Delivery method |
| `delivery.pickup_location` | string | ✗ | Order-delivery adapter | Pickup location |
| `delivery.delivery_location` | string | ✗ | Order-delivery adapter | Delivery location |
| `payment.status` | string | ✓ | Payment adapter | "INITIATED", "ACCEPTED", "PENDING" |
| `payment.deposit_id` | string | ✗ | Payment adapter | PawaPayAPI deposit ID |
| `totals.subtotal` | int | ✓ | Cart-order adapter | Confirmed subtotal |
| `totals.delivery` | int | ✓ | Delivery adapter | Confirmed delivery fee |
| `totals.tax` | int | ✗ | Manual | Confirmed tax |
| `totals.grand_total` | int | ✓ | Cart-order adapter | Confirmed grand total |
| `confirmed_at` | ISO8601 | ✓ | Manual | Confirmation timestamp |
| `updated_at` | ISO8601 | ✓ | Manual | Record update time |

---

## 10. DELIVERY TASK BLOB

**Purpose:** Delivery task created after order confirmation

**Schema Version:** v1

**Postgres Table:** `ice_delivery_task`

**Redis TTL:** 30–180 minutes

**Adapter Dependencies:**
- Order-delivery adapter (task creation, code generation)
- Cart-order adapter (order reference)

### Fields

| Field | Type | Required | Source | Notes |
|-------|------|----------|--------|-------|
| `schema_version` | string | ✓ | Manual | "v1" |
| `delivery_task_id` | string | ✓ | Order-delivery adapter | Unique task ID |
| `order_id` | string | ✓ | Cart-order adapter | Associated order ID |
| `user_id` | string | ✓ | Manual | User/customer ID |
| `business_id` | string | ✓ | Manual | Business ID |
| `status` | string | ✓ | Order-delivery adapter | "INITIATED", "IN_TRANSIT", "DELIVERED" |
| `delivery_code` | string | ✓ | Order-delivery adapter | Verification code |
| `pickup_location` | string | ✗ | Order-delivery adapter | Where to pick up |
| `delivery_location` | string | ✗ | Order-delivery adapter | Where to deliver |
| `estimated_delivery_time` | ISO8601 | ✗ | Order-delivery adapter | ETA |
| `created_at` | ISO8601 | ✓ | Order-delivery adapter | Task creation time |
| `updated_at` | ISO8601 | ✓ | Manual | Record update time |

---

## 11. AFFILIATE SESSION CONTEXT BLOB

**Purpose:** Affiliate tracking info attached to user session

**Schema Version:** v1

**Postgres Table:** `ice_affiliate_session_context`

**Redis TTL:** 1–24 hours

**Adapter Dependencies:**
- Affiliate adapter (code resolution, campaign info)

### Fields

| Field | Type | Required | Source | Notes |
|-------|------|----------|--------|-------|
| `schema_version` | string | ✓ | Manual | "v1" |
| `session_id` | string | ✓ | Bot-session adapter | Session ID |
| `affiliate.code` | string | ✓ | Affiliate adapter | Affiliate code (e.g., "aff-code-123") |
| `affiliate.source` | string | ✓ | Affiliate adapter | "link", "direct", "referral" |
| `affiliate.campaign` | string | ✗ | Affiliate adapter | Campaign name |
| `affiliate.first_seen_at` | ISO8601 | ✓ | Affiliate adapter | When code first seen |
| `affiliate.last_seen_at` | ISO8601 | ✓ | Affiliate adapter | Last activity with this code |
| `updated_at` | ISO8601 | ✓ | Manual | Record update time |

---

## 12. ORDER ATTRIBUTION BLOB

**Purpose:** Attribution of an order to an affiliate

**Schema Version:** v1

**Postgres Table:** `ice_order_attribution`

**Redis TTL:** 30–120 minutes

**Adapter Dependencies:**
- Affiliate adapter (attribution event emission)
- Cart-order adapter (order reference)

### Fields

| Field | Type | Required | Source | Notes |
|-------|------|----------|--------|-------|
| `schema_version` | string | ✓ | Manual | "v1" |
| `attribution_id` | string | ✓ | Affiliate adapter | Unique attribution ID |
| `order_id` | string | ✓ | Cart-order adapter | Associated order ID |
| `user_id` | string | ✓ | Manual | User ID |
| `business_id` | string | ✓ | Manual | Business ID |
| `affiliate_code` | string | ✓ | Affiliate adapter | Affiliate code |
| `affiliate_id` | string | ✗ | Affiliate adapter | Affiliate ID (if resolved) |
| `session_id` | string | ✗ | Bot-session adapter | Session ID |
| `status` | string | ✓ | Affiliate adapter | "attributed", "pending", "rejected" |
| `created_at` | ISO8601 | ✓ | Affiliate adapter | Attribution creation time |
| `updated_at` | ISO8601 | ✓ | Manual | Record update time |

---

## 13. AFFILIATE PERFORMANCE SUMMARY BLOB

**Purpose:** Cached affiliate metrics (for dashboards)

**Schema Version:** v1

**Postgres Table:** `ice_affiliate_perf_summary`

**Redis TTL:** 5–60 minutes

**Adapter Dependencies:**
- Affiliate adapter (earnings, attribution counts)

### Fields

| Field | Type | Required | Source | Notes |
|-------|------|----------|--------|-------|
| `schema_version` | string | ✓ | Manual | "v1" |
| `affiliate_id` | string | ✓ | Affiliate adapter | Affiliate ID |
| `affiliate_code` | string | ✓ | Affiliate adapter | Affiliate code |
| `window.from` | ISO8601 | ✓ | Manual | Window start date |
| `window.to` | ISO8601 | ✓ | Manual | Window end date |
| `metrics.clicks` | int | ✓ | Affiliate adapter | Unique clicks |
| `metrics.attributions` | int | ✓ | Affiliate adapter | Attributed orders |
| `metrics.paid_attributions` | int | ✓ | Affiliate adapter | Paid/confirmed orders |
| `metrics.sales_volume_zmw` | float | ✓ | Affiliate adapter | Commission amount |
| `metrics.unique_buyers` | int | ✓ | Affiliate adapter | Unique customers |
| `metrics.conversion_quality` | float | ✓ | Affiliate adapter | paid_attributions / clicks |
| `tier.name` | string | ✗ | Affiliate adapter | "bronze", "silver", "gold" |
| `tier.multiplier` | float | ✗ | Affiliate adapter | Commission multiplier |
| `updated_at` | ISO8601 | ✓ | Manual | Summary generation time |

---

## Adapter-to-Blob Dependency Matrix

| Adapter | Blobs It Populates | Key Fields |
|---------|-------------------|-----------|
| **Bot-session** | Bot Core, Session Snapshot, Hydrated Session Context | stats, session_state, user.profile |
| **MSME** | Owner Profile, Hydrated Session Context | business.*, user.preferences |
| **Catalog/Inventory** | Catalog Index, Product Snapshot, Hydrated Session Context | product_ids, inventory.*, catalog.* |
| **Cart-Order** | Cart, Order Draft, Order Confirmation | items, totals, order_id |
| **Payment** | Order Confirmation, Order Draft | payment.method, payment.deposit_id |
| **Delivery** | Order Draft, Order Confirmation, Delivery Task | delivery.method, delivery_code, totals.delivery |
| **Affiliate** | Affiliate Session Context, Order Attribution, Affiliate Performance Summary | affiliate.code, affiliate_id, metrics.* |

---

## Postgres Tables Schema

```sql
-- Session and user context
CREATE TABLE ice_bot_core (
  bot_id VARCHAR PRIMARY KEY,
  blob JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ice_owner_profile (
  owner_id VARCHAR PRIMARY KEY,
  business_id VARCHAR NOT NULL,
  blob JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ice_session_snapshot (
  session_id VARCHAR PRIMARY KEY,
  user_id VARCHAR NOT NULL,
  bot_id VARCHAR NOT NULL,
  blob JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Catalog and inventory
CREATE TABLE ice_catalog_index (
  business_id VARCHAR PRIMARY KEY,
  blob JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ice_product_snapshot (
  product_id VARCHAR PRIMARY KEY,
  business_id VARCHAR NOT NULL,
  blob JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Hydrated session (main ICE blob)
CREATE TABLE ice_hydrated_session (
  session_id VARCHAR PRIMARY KEY,
  user_id VARCHAR NOT NULL,
  business_id VARCHAR NOT NULL,
  blob JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Cart and order
CREATE TABLE ice_cart (
  cart_id VARCHAR PRIMARY KEY,
  user_id VARCHAR NOT NULL,
  business_id VARCHAR NOT NULL,
  blob JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ice_order_draft (
  order_id VARCHAR PRIMARY KEY,
  user_id VARCHAR NOT NULL,
  business_id VARCHAR NOT NULL,
  blob JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ice_order_confirmed (
  order_id VARCHAR PRIMARY KEY,
  user_id VARCHAR NOT NULL,
  business_id VARCHAR NOT NULL,
  blob JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Delivery
CREATE TABLE ice_delivery_task (
  delivery_task_id VARCHAR PRIMARY KEY,
  order_id VARCHAR NOT NULL,
  user_id VARCHAR NOT NULL,
  business_id VARCHAR NOT NULL,
  blob JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Affiliate
CREATE TABLE ice_affiliate_session_context (
  session_id VARCHAR PRIMARY KEY,
  blob JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ice_order_attribution (
  attribution_id VARCHAR PRIMARY KEY,
  order_id VARCHAR NOT NULL,
  user_id VARCHAR NOT NULL,
  business_id VARCHAR NOT NULL,
  blob JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ice_affiliate_perf_summary (
  affiliate_id VARCHAR NOT NULL,
  window_from DATE NOT NULL,
  window_to DATE NOT NULL,
  blob JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (affiliate_id, window_from, window_to)
);
```

---

## Redis Key Patterns & TTLs

```
# Bot-centric
bot:core:{bot_id}                        → 5–30m
bot:owner:{owner_id}                    → 6–24h
bot:catalog:index:{business_id}         → 30–120m
bot:catalog:product:{product_id}        → 1–10m

# Session-centric
session:snapshot:{session_id}           → 5–30m
session:ctx:{session_id}                → 10–30m  (hydrated)
session:affiliate:{session_id}          → 1–24h

# Cart and order
cart:{cart_id}                          → 5–30m
order:draft:{order_id}                  → 10–60m
order:confirmed:{order_id}              → 30–120m

# Delivery
delivery:task:{delivery_task_id}        → 30–180m

# Affiliate
affiliate:attr:{attribution_id}         → 30–120m
affiliate:perf:{affiliate_id}:{date}    → 5–60m

# Locking
lock:hydrate:{session_id}               → 10–30s   (single-flight)
neg:hydrate:{session_id}                → 10–60s   (negative cache)
```

---

## Versioning & Migration Strategy

All blobs include `schema_version` field. Migration approach:

1. **Read-time transform:** When loading from Postgres/Redis, check `schema_version` and apply transforms if needed.
2. **Write-time upgrade:** When updating a blob, upgrade to latest schema before writing.
3. **Example versioning:**
   - `v1` → baseline
   - `v2` → add new field (optional, backward-compatible)
   - `v3` → rename or restructure (requires migration)

---

## Next Steps

1. Create Postgres models for all tables (using SQLAlchemy ORM)
2. Create repository layer (CRUD operations with JSONB queries)
3. Implement Redis client wrapper with TTL management
4. Update hydrate workflow to populate all blobs atomically
5. Add schema validation before persisting (Pydantic models per blob type)
