# Backend Stack - Service-to-Service Architecture & E2E Automation

## High-Level Data Flow

```
┌─────────────┐
│   BOT APP   │ (User interaction)
└──────┬──────┘
       │
       ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                         ICE SERVICE (Orchestration)                        │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  Adapters:                                                          │  │
│  │  • Bot Session  • MSME Auth   • Catalog/Inventory  • Cart/Order   │  │
│  │  • Payment      • Delivery    • Affiliate          • MSME Profile  │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────┘
       │                    │                │                │
       ├────────────────────┼────────────────┼────────────────┤
       │                    │                │                │
       ▼                    ▼                ▼                ▼
   ┌─────────┐      ┌────────────┐   ┌──────────────┐  ┌───────────────┐
   │ BOT     │      │ MSME       │   │ CATALOG      │  │ CART / ORDER  │
   │ SESSION │      │ ENGINE     │   │ INVENTORY    │  │ DELIVERY      │
   │ :8000   │      │ :8500      │   │ :8520        │  │ :8560         │
   └────┬────┘      └──────┬─────┘   └──────┬───────┘  └───────┬───────┘
        │                  │                │                 │
        │                  │                │                 │
        └──────────────┬───┴────────────────┴─────────────────┘
                       │
                       ▼
            ┌────────────────────┐
            │ PAYMENT REVENUE    │
            │ :8590              │
            └────────┬───────────┘
                     │
                     ▼
            ┌────────────────────┐
            │ AFFILIATE ENGINE   │
            │ :8510              │
            └────────┬───────────┘
                     │
                     ▼
            ┌────────────────────┐
            │ AUDIT SERVICE      │
            │ :8290              │
            └────────────────────┘
```

## Detailed Service Relationships & Automations

### 1. SESSION INITIALIZATION FLOW
```
Bot App
   │
   ├─[POST /session/create]──────────► BOT SESSION (:8000)
   │                                      │
   │◄─ session_id, initial_state ◄───────┤
   │
   └─[Session created event]─────────► MSME AUTH (:8500)
                                          │
                                          ├─ Verify user phone
                                          │
                                          └─► AUDIT SERVICE (:8290)
                                                  │
                                                  └─ Log: user_session_created
```

### 2. CATALOG HYDRATION FLOW
```
ICE Service (hydrate workflow)
   │
   ├─[GET /catalog/business/{id}]──────────────► CATALOG/INVENTORY (:8520)
   │                                               │
   │                                               ├─ Fetch products
   │                                               │
   │                                               └─[GET /inventory/{variant_id}]
   │                                                  │
   │◄─ products + inventory (stock_level, reserved) ◄┤
   │
   ├─ Cache in Redis (TTL: 5m)
   │
   └─ Store in Postgres (session blob)
      │
      └─► AUDIT SERVICE (:8290)
             └─ Log: catalog_hydrated
```

### 3. CART DRAFT → ORDER CONFIRMATION FLOW
```
Bot Session
   │
   ├─[POST /cart/add-item]─────────────► CART (:8530)
   │                                       │
   │◄─ draft_id, line_items ◄─────────────┤
   │
   │
   ├─[Reserve inventory]───────────────► CATALOG/INVENTORY (:8520)
   │                                       │
   │◄─ reservation_id ◄────────────────────┤
   │
   │
   ├─[POST /orders/create]────────────► ORDER/DELIVERY (:8560)
   │  (includes pickup/delivery location)
   │                                       │
   │◄─ order_id, status:PENDING ◄─────────┤
   │
   │
   ├─[POST /initiate_payment]─────────► PAYMENT REVENUE (:8590)
   │  (numeric phone normalization)        │
   │                                       ├─ Call PawaPayAPI
   │                                       │
   │◄─ deposit_id, status:ACCEPTED ◄──────┤
   │
   │
   ├─ Store OOB (Order Out of Band)
   │  in Postgres JSONB
   │
   └─► AUDIT SERVICE (:8290)
          └─ Log: order_confirmed, payment_initiated
```

### 4. DELIVERY TASK CREATION FLOW
```
After Payment Confirmation
   │
   ├─[POST /delivery/initiate/{order_id}]──► ORDER/DELIVERY (:8560)
   │                                           │
   │                                           ├─ Generate delivery code
   │                                           │
   │◄─ delivery_task_id ◄──────────────────────┤
   │
   └─► NOTIFICATION (:8570)
          └─ In-app: "Delivery initiated"
```

### 5. AFFILIATE ATTRIBUTION FLOW
```
After Order Confirmed
   │
   ├─[GET /a/{affiliate_code}/resolve]──► AFFILIATE ENGINE (:8510)
   │                                        │
   │◄─ affiliate_id, commission_rate ◄─────┤
   │
   │
   ├─[POST /attribute/order]────────────► AFFILIATE ENGINE (:8510)
   │  (order_id, business_id, amount)       │
   │                                        ├─ Record attribution
   │                                        │
   │◄─ attribution_id, status:attributed ◄┤
   │
   │
   └─ Store affiliate context in Postgres
      │
      └─► AUDIT SERVICE (:8290)
             └─ Log: attribution_recorded, commission_calculated
```

### 6. BUSINESS PROFILE ENRICHMENT FLOW
```
MSME Context Hydration
   │
   ├─[GET /business/{id}]──────────────► MSME ENGINE (:8500)
   │                                      │
   │                                      ├─ Fetch profile
   │                                      │
   │◄─ name, owner, location, tags ◄─────┤
   │
   │
   ├─[GET /business/{id}/entitlements]─► MSME ENGINE (:8500)
   │                                      │
   │                                      ├─ Fetch subscription plan
   │                                      │
   │◄─ plan, features, limits ◄──────────┤
   │
   │
   └─ Store business context in Postgres
      (subscription constraints, feature flags)
```

### 7. PERSISTENCE LAYER ORCHESTRATION
```
All Workflows
   │
   ├─► POSTGRES (:5432)
   │   ├─ ice_sessions (JSONB blob)
   │   ├─ ice_order_drafts (JSONB blob)
   │   ├─ ice_attributions (affiliate context)
   │   └─ audit_log (all events)
   │
   ├─► REDIS (:6379)
   │   ├─ cache:session:{id} (TTL: 30m)
   │   ├─ cache:catalog:{business_id} (TTL: 5m)
   │   ├─ lock:hydrate:{session_id} (single-flight)
   │   ├─ neg:hydrate:{session_id} (failure cache)
   │   └─ streams:ice:hydrated (event stream)
   │
   └─► NEXTCLOUD (:8080)
       └─ Media uploads (product images)
```

## End-to-End Example: User Places Order

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        USER PLACES ORDER (E2E)                              │
└─────────────────────────────────────────────────────────────────────────────┘

STEP 1: Session Initialization
┌──────────────────────────────────────┐
│ Bot App                              │
├──────────────────────────────────────┤
│ [1] POST /session/create             │
│     payload: {phone, business_id}    │
└──────────────────┬───────────────────┘
                   │ (via ICE Adapter)
                   ▼
            BOT SESSION (:8000)
            ├─ Create session record
            ├─ Initialize Redis stream
            ├─ Return session_id
            │
            └──► MSME ENGINE (:8500)
                 ├─ Verify user exists
                 ├─ Fetch business profile
                 │
                 └──► AUDIT SERVICE (:8290)
                      └─ Log: session_created


STEP 2: Catalog Hydration
┌──────────────────────────────────────┐
│ ICE Service (hydrate workflow)       │
├──────────────────────────────────────┤
│ [2] Compose session blob             │
│     ├─ User info from MSME           │
│     ├─ Business policies from MSME   │
│     └─ Catalog from CATALOG/INVENTORY│
└──────────────────┬───────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
   CATALOG/INVENTORY    MSME ENGINE
   ├─ GET /catalog/     ├─ GET /business/
   │    business/{id}   │    {id}
   │                    │
   └─ Get variants  &   └─ Get entitlements
     stock levels


STEP 3: Add to Cart & Reserve
┌──────────────────────────────────────┐
│ Bot Session (user shopping)          │
├──────────────────────────────────────┤
│ [3] Add product to cart              │
│     payload: {product_id, qty}       │
└──────────────────┬───────────────────┘
                   │ (via ICE Adapter)
                   ▼
            CART (:8530)
            ├─ Create draft
            └─► CATALOG/INVENTORY (:8520)
                ├─ Reserve qty from stock_level
                └─ Decrement available count


STEP 4: Confirm Order & Initiate Payment
┌──────────────────────────────────────┐
│ Bot Session (checkout)               │
├──────────────────────────────────────┤
│ [4] Confirm order                    │
│     payload: {                       │
│       items,                         │
│       delivery_method,               │
│       pickup_location,               │
│       payment_number (phone)         │
│     }                                │
└──────────────────┬───────────────────┘
                   │ (via ICE Adapter)
                   ▼
        ┌──────────────────────────────┐
        │ ORDER/DELIVERY (:8560)       │
        ├──────────────────────────────┤
        │ [4a] Create order            │
        │  POST /orders/create         │
        │  ├─ Store items              │
        │  ├─ Store locations in meta  │
        │  └─ status: CONFIRMED        │
        │                              │
        └────────────┬─────────────────┘
                     │
                     ▼
        ┌──────────────────────────────┐
        │ PAYMENT REVENUE (:8590)      │
        ├──────────────────────────────┤
        │ [4b] Initiate payment        │
        │  POST /deposits/initiate     │
        │  ├─ Normalize payment_number │
        │  │  (strip non-digits)       │
        │  ├─ Call PawaPayAPI          │
        │  └─ status: ACCEPTED         │
        │                              │
        └────────────┬─────────────────┘
                     │
                     ▼
        ┌──────────────────────────────┐
        │ AUDIT SERVICE (:8290)        │
        ├──────────────────────────────┤
        │ Log:                         │
        │ • order_created              │
        │ • payment_initiated          │
        │ • idempotency_key (replay)   │
        └──────────────────────────────┘


STEP 5: Create Delivery Task
┌──────────────────────────────────────┐
│ ICE Service (confirm workflow)       │
├──────────────────────────────────────┤
│ [5] After payment confirmed          │
│     POST /delivery/initiate/{order_id}
└──────────────────┬───────────────────┘
                   │
                   ▼
            ORDER/DELIVERY (:8560)
            ├─ Generate delivery code
            ├─ status: INITIATED
            └──► NOTIFICATION (:8570)
                 └─ Send: "Delivery initiated"


STEP 6: Record Affiliate Attribution
┌──────────────────────────────────────┐
│ ICE Service (confirm workflow)       │
├──────────────────────────────────────┤
│ [6] Emit attribution event           │
└──────────────────┬───────────────────┘
                   │
                   ▼
            AFFILIATE ENGINE (:8510)
            ├─ POST /attribute/order
            ├─ Record conversion
            ├─ Calculate commission
            └──► NOTIFICATION (:8570)
                 └─ Send: "Commission earned"


STEP 7: Persist State & Emit Events
┌──────────────────────────────────────┐
│ ICE Service (persistence layer)      │
├──────────────────────────────────────┤
│ [7] Store final OOB state            │
└──────────────────┬───────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
    POSTGRES (:5432)      REDIS (:6379)
    ├─ ice_sessions       ├─ streams:ice:hydrated
    ├─ ice_order_drafts   ├─ cache:order:{id}
    ├─ ice_attributions   └─ streams:ice:confirmed
    └─ audit_log


FINAL STATE
┌──────────────────────────────────────┐
│ User Notifications                   │
├──────────────────────────────────────┤
│ ✓ "Order confirmed"                  │
│ ✓ "Payment accepted"                 │
│ ✓ "Delivery initiated"               │
│ ✓ "Affiliate commission recorded"    │
└──────────────────────────────────────┘
```

## Key Automations

| Automation | Trigger | Actions | Services |
|-----------|---------|---------|----------|
| **Session Hydration** | Session created | Fetch user profile, business policies, catalog | MSME, Catalog, Audit |
| **Inventory Reserve** | Item added to cart | Decrement stock, create reservation | Catalog/Inventory |
| **Order Confirmation** | Checkout submit | Create order, initiate payment | Order/Delivery, Payment |
| **Payment Initiation** | Order confirmed | Normalize payment number, call PawaPayAPI | Payment, Audit |
| **Delivery Task** | Payment accepted | Generate delivery code, notify user | Order/Delivery, Notification |
| **Affiliate Attribution** | Order confirmed | Resolve affiliate, record conversion, calc commission | Affiliate, Notification, Audit |
| **State Persistence** | Any mutation | Write JSONB to Postgres, cache in Redis | Postgres, Redis |
| **Audit Trail** | All events | Log with correlation_id, event_type, timestamp | Audit Service |
| **Idempotency** | Retry request | Return cached response for same idempotency_key | Postgres, Redis |

## Error Handling & Resilience

```
┌─ Service Unavailable
│  ├─ Catalog: return empty product list (graceful degrade)
│  ├─ Payment: queue for retry with exponential backoff
│  ├─ Delivery: defer task creation until available
│  └─ MSME: skip policy enrichment, proceed with defaults
│
├─ Validation Errors
│  ├─ Payment number invalid: normalize (strip non-digits)
│  ├─ Inventory unavailable: return OUT_OF_STOCK error
│  ├─ Business not found: return 404 or skip enrichment
│  └─ Affiliate not found: proceed without attribution
│
└─ Duplicate Prevention
   ├─ Idempotency key replay: return cached response
   ├─ Single-flight locks: prevent parallel hydrations
   ├─ Negative cache: avoid retrying failed operations
   └─ Deduplication: deduplicate events before processing
```

## Deployment Topology

```
LOCAL (Docker Compose)          PRODUCTION (Kubernetes)
───────────────────────────      ──────────────────────

localhost:8000  ◄─►             bot-session-service
localhost:8500  ◄─►             msme-engine-service
localhost:8510  ◄─►             affiliate-engine-service
localhost:8520  ◄─►             catalog-inventory-service
localhost:8530  ◄─►             cart-service
localhost:8560  ◄─►             order-delivery-service
localhost:8590  ◄─►             payment-revenue-service
localhost:5432  ◄─►             postgres-statefulset
localhost:6379  ◄─►             redis-statefulset
localhost:8290  ◄─►             audit-service
localhost:8570  ◄─►             notification-service
localhost:8080  ◄─►             nextcloud-service

All via Docker network           All via K8s cluster DNS
                                 (service-name.namespace.svc.cluster.local)
```
