# Backend Architecture - Full System Flow

## 🎯 Core Services (7 Backend Services)

### Service Ports & Responsibilities:

```
MSME Engine (8500)          - Business, user, roles, auth
├─ /businesses/{id}         - Get business profile
├─ /auth/login              - JWT token
└─ /auth/register           - Create user

Catalog-Inventory (8520)    - Products, inventory, media
├─ /catalog/{business_id}   - Product list
├─ /inventory/{variant_id}  - Stock levels
└─ /media/upload            - Product images

Cart Service (8530)         - Shopping cart operations
├─ /cart/create             - New cart
├─ /cart/{id}/add-item      - Add to cart
└─ /cart/{id}/checkout      - Prepare for order

Order-Delivery (8560)       - Orders, fulfillment
├─ /orders/create           - Create order
├─ /orders/{id}/initiate_payment - Start payment flow
└─ /delivery/{order_id}     - Delivery task

Payment-Revenue (8590)      - Payments, callbacks
├─ /callbacks/pawapay/deposits - Payment webhook
├─ /payments/{id}/status    - Check payment status
└─ /revenue/reconcile       - Revenue tracking

Notification (8570)         - Messages, alerts
├─ /send/sms                - Send SMS
└─ /send/email              - Send email

Affiliate Engine (8510)     - Commissions, attribution
├─ /attributions            - List attributions
├─ /attributions/create     - Record attribution
└─ /commissions/{aff_id}    - Get commissions
```

## 📊 End-to-End User Journey

### **Step 1: User Initiates Order (Ingress consumes incoming message)**
```
WhatsApp message: "I want rice"
        ↓
incoming-messages stream (Redis)
        ↓
Ingress Service
        ↓
calls ICE /hydrate/session
```

### **Step 2: ICE Hydrates Session (Central Orchestration)**
```
ICE receives: {session_id, user_phone, bot_id}
        ↓
Calls MSME Engine (8500):
  GET /business/{business_id}
  └─ Returns: business profile, policies
        ↓
Calls Catalog-Inventory (8520):
  GET /catalog/{business_id}
  └─ Returns: products, prices, inventory levels
        ↓
Calls Cart (8530):
  GET /cart/{session_id}
  └─ Returns: current cart items
        ↓
Compose Session Blob (JSONB):
{
  session_id,
  user_phone,
  business_context: {name, category, policies},
  catalog_context: {rice: K180, flour: K250, stock},
  session_state: {cart_items: [], total: 0}
}
        ↓
Cache in Redis (30min TTL)
Store in Postgres JSONB
        ↓
Return to Ingress
```

### **Step 3: Bot Processes Message with Session Blob**
```
Bot sees session_blob with catalog
        ↓
User: "Add rice to cart"
        ↓
Bot calls Cart (8530):
  POST /cart/{session_id}/add-item
  {product_id: "rice", quantity: 2, price: 180}
```

### **Step 4: User Confirms Order (Checkout)**
```
Bot: "Total K360. Confirm?"
User: "Yes"
        ↓
Ingress calls ICE /reserve
        ↓
ICE calls Cart (8530):
  POST /cart/{id}/checkout
  └─ Returns: order_draft_id
        ↓
Cache draft in Redis (60min TTL)
        ↓
Return to Ingress
```

### **Step 5: Payment Initiation**
```
Bot: "Choose payment method"
User: "MTN Mobile Money"
        ↓
Ingress calls ICE /confirm
        ↓
ICE calls Order-Delivery (8560):
  POST /orders/create
  {business_id, user_phone, items: [...], total: 360}
  └─ Returns: order_id
        ↓
ICE calls Order-Delivery (8560):
  POST /orders/{order_id}/initiate_payment
  {provider: "MTN_MOMO_ZMB", phone: "+260973456789"}
  └─ Returns: external_id (payment request reference)
        ↓
Store order_confirmed blob in Postgres
Cache in Redis (120min TTL)
        ↓
Return order_id to Ingress
```

### **Step 6: User Approves Payment (Asynchronous)**
```
User receives USSD prompt: "Approve MTN payment for K360? Reply #1"
        ↓
Payment Provider (MTN) processes
        ↓
Payment-Revenue (8590) receives webhook:
  POST /callbacks/pawapay/deposits
  {
    depositId: "{external_id}",
    status: "COMPLETED",
    amount: "360",
    currency: "ZMW"
  }
        ↓
Payment service updates order status to PAID
Publishes payment:completed event
        ↓
Background Dispatcher consumes event
Triggers delivery task creation
Triggers affiliate attribution
```

### **Step 7: Delivery Coordination**
```
Background Dispatcher sees payment:completed event
        ↓
Calls Order-Delivery (8560):
  POST /delivery/create
  {order_id, location, recipient_phone}
  └─ Returns: delivery_id
        ↓
Creates delivery task blob
Stores in Postgres
        ↓
Notification (8570) sends SMS:
  "Order confirmed! Delivery on Feb 6, K360. Ref: DEL2025000001"
```

### **Step 8: Affiliate Attribution**
```
Dispatcher sees payment:completed event
        ↓
Checks if affiliate_id in order metadata
        ↓
Calls Affiliate Engine (8510):
  POST /attributions/create
  {
    order_id,
    affiliate_id,
    business_id,
    amount: 360,
    commission_rate: 10%
  }
        ↓
Affiliate service calculates commission: K36
Stores attribution record
Publishes attribution:recorded event
```

### **Step 9: Bot Confirms Delivery Status**
```
Ingress polls ICE /orders/{order_id}/status
        ↓
ICE fetches from Postgres order_confirmed blob
        ↓
Returns: {status: "PAID", delivery_id, expected_date}
        ↓
Bot sends to user:
  "✅ Order confirmed!
   🚚 Delivery: Feb 6, 2026
   💰 Amount: K360 (K36 voucher added)
   Reference: DEL2025000001"
```

## 🔄 Script Examples (from /scripts/)

### 1. **insert_test_business.py**
Creates test data in MSME Engine SQLite:
- Business record
- User/Owner record
- Role record

### 2. **bulk_product_simulation.py**
```python
# For each of 10 businesses:
#   - Create category
#   - Create 5 products (name, price, SKU)
#   - Create variants
#   - Add inventory (50 units each)
#
# Uses Catalog-Inventory API:
POST /catalog/category
POST /catalog/product
POST /catalog/product/{id}/variant
POST /inventory/update
```

### 3. **test_cart_catalog_flow.py**
```
1. Fetch product from Catalog (8520)
   GET /catalog/business/{id}
        ↓
2. Check inventory
   GET /inventory/{variant_id}
        ↓
3. Create cart
   POST /cart/create
        ↓
4. Add item to cart
   POST /cart/{id}/add-item
        ↓
5. Validate product exists, stock available
```

### 4. **test_order_payment_flow.py**
```
1. Get auth token
   POST /auth/login @ MSME (8500)
        ↓
2. Create order
   POST /orders/create @ Order-Delivery (8560)
        ↓
3. Initiate payment
   POST /orders/{id}/initiate_payment @ Order-Delivery (8560)
        ↓
4. Receive external_id (payment reference)
```

### 5. **test_e2e_affiliate_id.py** (Full E2E)
```
1. Get token
2. Create order with affiliate_id metadata
3. Initiate payment → get external_id
4. Simulate payment callback (COMPLETED)
5. Wait for dispatcher
6. Check affiliate attribution created
```

## 🗂️ Data Flow Summary

```
┌─────────────────────────────────────────────────────┐
│           INCOMING MESSAGE (WhatsApp)                │
└──────────────────┬──────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────┐
│  INGRESS SERVICE (consumes incoming-messages stream) │
└──────────────────┬──────────────────────────────────┘
                   ↓
        ┌──────────────────────┐
        │  ICE SERVICE (5100)  │  ← Central Hub
        │  (Orchestrator)      │
        └──────┬───────┬───────┘
         ┌─────┴──────┬┴────┬──────────┐
         ↓            ↓     ↓         ↓
    MSME (8500)  Catalog  Cart   Order-Delivery
                 (8520)   (8530)   (8560)
                                     ↓
                        ┌────────────┼─────────┐
                        ↓            ↓         ↓
                    Payment (8590)  Notify  Affiliate
                                   (8570)  Engine (8510)
                        ↓
                  Payment Callback
                    (Webhook)
                        ↓
            Background Dispatcher
                (consumes events)
                        ↓
            Updates Order Status
            Creates Delivery Task
            Records Attribution
                        ↓
┌─────────────────────────────────────────────────────┐
│  OUTGOING MESSAGE (WhatsApp Confirmation)           │
└─────────────────────────────────────────────────────┘
```

## 🎯 Key Patterns

### **Synchronous (Blocking) - When User Waiting:**
- `/hydrate/session` - Get session context (< 500ms with cache)
- `/reserve` - Lock inventory (< 1s)
- `/confirm` - Create order (< 2s)

### **Asynchronous (Background) - Eventual Consistency:**
- Payment callbacks → Dispatcher → delivery + attribution
- Notifications sent in background
- Audit events appended to stream

### **Caching Strategy:**
- Session blob: 30min (catalog can change)
- Order draft: 60min (reservation lock)
- Order confirmed: 120min (immutable)
- Catalog snapshot: 5min (high-churn)
- Idempotency cache: 2-4h (duplicate prevention)

### **Error Handling:**
- OUT_OF_STOCK → suggest alternatives
- PRICE_CHANGED → re-quote
- PAYMENT_FAILED → retry or manual intervention
- DELIVERY_UNAVAILABLE → fallback to pickup

## 📈 Scale Points

- **ICE can handle:** 1000 req/s (with caching)
- **Catalog searches:** Cached → instant
- **Reservations:** Serialized on inventory (1-10 req/s per product)
- **Payments:** Async → no blocking
- **Affiliate attribution:** Batch processed

---

**Bottom Line:** ICE is the API gateway that orchestrates all 7 backend services into a coherent user journey. Ingress stays simple, backends stay independent, and the contract between them (session blob) stays stable.
