# Backend ↔ ICE (Bot) Integration Context

## Purpose

This document groups the **current backend compose stack** and **bot services (ICE-first)** into one unified view, focused on how the backend should connect to ICE to provide Redis JSONB state as referenced in bot docs.

---

## 1) System View (High Level)

### Backend Services (Current Compose Stack)
- **affiliate-engine**: affiliate attribution, epochs, allocations, payouts
- **payment-revenue**: payments, revenue, payout initiation/callbacks
- **msme-engine**: MSME onboarding and business profile
- **order/cart/catalog/notification/delivery**: workflow services (existing in repo)
- **postgres**: primary persistence for backend domains

### Bot Layer (ICE-first architecture)
- **bot-ingress-service**: normalize + enrich + route to bot lanes
- **default-bot-service**: tree/menu flows (public/affiliate/MSME)
- **custom-bot-service**: node engine + OOB (order object builder)
- **bot-intent-service**: intent resolution via Gemini
- **reply-service**: reply generation
- **outbound-service**: WhatsApp/SMS/web delivery
- **ICE-service**: integration/consolidation boundary between bot layer and backend

**Key principle**: bot layer depends ONLY on Redis streams/cache and ICE API contract. Backend services integrate behind ICE.

---

## 2) Integration Contract Boundary (ICE)

ICE is the **single entry point** for bot services to reach backend domains. ICE provides **cache-first JSONB state** in Redis and coordinates authoritative operations against backend services.

### ICE Responsibilities
- Provide **hydration** for session state and order object
- Provide **reservation** for cart checkout (price + inventory lock)
- Provide **confirmation** for payment/order finalization
- Emit async **preload** and **hydrated** events for bot services
- Persist **audit patches** and materialize JSONB snapshots

### Backend Responsibilities
- Implement domain APIs for ICE to call (catalog, cart/order, payment, delivery, affiliate attribution)
- Enforce idempotency on callbacks
- Provide reference data required for hydration (catalog, business profile, policies)

---

## 3) Redis JSONB Shapes (ICE Cache)

These are the **canonical JSONB blobs** ICE should write to Redis to power bot session flows:

### Session Cache
Key: `cache:session:{session_id}`
```json
{
  "session_id": "sess_abc123",
  "current_node": "serve_products",
  "mode": "public|registered",
  "role": "customer|msme|affiliate|staff",
  "intent_required": false,
  "last_active_at": "2026-02-04T10:30:00Z",
  "schema_version": "1.0",
  "hydrated_at": "2026-02-04T10:25:00Z",
  "stale": false
}
```

### Order Draft / OOB Cache
Key: `cache:oob:{session_id}`
```json
{
  "order_id": "tmp_ord_987",
  "session_id": "sess_abc123",
  "items": [],
  "totals": {"subtotal": 0.0, "delivery_fee": 0.0, "grand_total": 0.0},
  "fulfillment": {},
  "payment": {"method": null, "status": "pending"},
  "attribution": {"business_id": "biz_456", "affiliate_id": "aff_789"},
  "metadata": {
    "schema_version": "2.0",
    "hydrated_at": "2026-02-04T10:15:00Z",
    "lock_version": 5
  }
}
```

### Bot Enrichment Cache
- `cache:bot:{phone}`
- `cache:user:{phone}`
- `cache:capabilities:{mode}`

These enable cache-first ingress processing and reduce backend lookups.

---

## 4) Streams & Event Flows

### Bot Layer Streams
- `ingress:incoming` → raw inbound payloads
- `ingress:resolved_payload` → enriched payload audit
- `bot:lane:default` / `bot:lane:custom` → bot execution lanes
- `intent:requests` / `intent:results` → intent resolution
- `reply:requests` / `outbound:requests` → message delivery
- `oob:audit` → order object patch stream
- `ice:preload` / `ice:hydrated` → hydration workflows

### ICE ↔ Backend Events
- **ICE** should publish `oob:audit` and `ice:hydrated`
- **Backend** should receive authoritative writes via ICE (not direct bot calls)

---

## 5) Backend ↔ ICE API Calls

These calls are **required** for bot workflows to use backend services indirectly.

### ICE Endpoints (Bot-facing)
- `POST /api/v1/hydrate/session`
  - Loads session, user, business, policy, and draft cart
  - Returns JSONB blobs + schema_version + hydrated_at

- `POST /api/v1/reserve`
  - Locks inventory/pricing for checkout
  - Returns reservation_id and TTL

- `POST /api/v1/confirm_order`
  - Finalizes order after payment
  - Creates records in Order + Payment services

### ICE Internal Calls (Backend-facing)
ICE should call backend services to satisfy the above:

**Catalog/Inventory**
- Get product availability and pricing snapshots

**Cart/Order**
- Create/update draft orders
- Reserve inventory
- Persist confirmed order

**Payment/Revenue**
- Create payment intent
- Confirm payment results

**Delivery**
- Validate delivery area/fee
- Create delivery task after order confirmation

**Affiliate Engine**
- Log attribution when affiliate_id present
- Emit commission events after payment success

**MSME Engine**
- Hydrate business profile and policies

---

## 6) Required Data Elements (Integration Rule)

All service-to-service calls/events MUST carry:
- `business_id`
- `user_phone`
- `session_id` (when bot-originated)
- `request_id` / `correlation_id`

Additionally:
- **Payment** and **delivery callbacks** MUST be idempotent.

---

## 7) Suggested Integration Map (Who calls whom)

```
Bot Layer
  └─→ ICE (HTTP + Streams)
        └─→ Backend Services (HTTP/gRPC)

Backend Services
  └─→ ICE (webhooks/streams for state hydration + audit)
```

### Why this grouping works
- Bot services remain stateless and stable
- ICE centralizes backend dependencies
- Backend services remain unchanged but become reachable via ICE
- Redis JSONB provides fast session and order state access

---

## 8) Next Implementation Steps

### Step 1: ICE Contract Alignment
- Confirm payload shapes with bot layer (hydrate/reserve/confirm)
- Freeze JSONB schemas and stream names

### Step 2: ICE Internal Adapters
Create adapters inside ICE for backend services:
- Catalog adapter
- Order/Cart adapter
- Payment adapter
- Delivery adapter
- Affiliate adapter
- MSME adapter

### Step 3: Cache + Audit
- Write session and OOB JSONB to Redis
- Append patches to `oob:audit`
- Emit `ice:hydrated` events

### Step 4: Integration Tests
- Simulate bot session → ICE hydration → backend calls
- Validate that bot services consume Redis JSONB without direct backend calls

---

## 9) Source References (Existing Docs)

- Bot architecture: [services/frontend/bot-services/bot architecture.txt](services/frontend/bot-services/bot%20architecture.txt)
- Default bot service: [services/frontend/bot-services/default-bot-service/ARCHITECTURE.md](services/frontend/bot-services/default-bot-service/ARCHITECTURE.md)
- Enhanced tree selection: [services/frontend/bot-services/default-bot-service/ENHANCED_PHASE2_ARCHITECTURE.md](services/frontend/bot-services/default-bot-service/ENHANCED_PHASE2_ARCHITECTURE.md)
- Custom bot service: [services/frontend/bot-services/custom-bot-service/ARCHITECTURE.md](services/frontend/bot-services/custom-bot-service/ARCHITECTURE.md)
- Ingress service: [services/frontend/bot-services/bot-ingress-service/README.md](services/frontend/bot-services/bot-ingress-service/README.md)
- Unified design: [docs/soft-launch-unified-design.md](docs/soft-launch-unified-design.md)
- Bot session workflows: [BOT_SESSION_WORKFLOWS.md](BOT_SESSION_WORKFLOWS.md)

---

## 10) Summary

This grouping keeps **bot services** independent and Redis-first while using **ICE** as the single integration boundary to the backend compose stack. The backend remains authoritative for business rules and persistence, while ICE provides **Redis JSONB state** to power bot session workflows.

**Outcome**: a clean separation of concerns with a single place (ICE) to adapt backend APIs for bot usage, without changing bot services.
