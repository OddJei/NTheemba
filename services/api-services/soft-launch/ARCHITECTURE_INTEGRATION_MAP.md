# Bot Services Architecture Integration Map
**Date:** February 6, 2026  
**Current State:** ICE Hydration Complete (Port 8100)  
**Task:** Integrate other bot services with new architecture

---

## Current Architecture Overview

### ✅ **Completed Layer (Orchestration)**
```
ICE Service (Port 8100)
├─ Two-phone hydration (from_number/to_number)
├─ Service token generation (JWT for auth)
├─ Bot auto-provisioning (custom type)
├─ Session state resolution (chat/cart/order/payment/delivery/closed)
├─ Expected action computation
├─ Catalog snapshots (11 products + variants)
├─ Affiliate context (optional)
├─ Cart context (state-dependent)
└─ Redis caching + event streaming
```

### 📊 **Port Mapping**
| Service | Port | Status | Notes |
|---------|------|--------|-------|
| ICE | 8100 | ✅ Running | Orchestration & hydration |
| Bot-Session | 8540 | ✅ Running | State mgmt + cycles |
| MSME | 8500 | ✅ Running | User/business/tokens |
| Catalog-Inventory | 8520 | ✅ Available | Product snapshots |
| Cart | 8530 | ✅ Available | Cart operations |
| Affiliate-Engine | 8510 | ✅ Available | Attribution tracking |
| Payment-Revenue | 8590 | ✅ Available | Payment processing |
| Order-Delivery | 8560 | ✅ Available | Delivery tracking |
| Audit-Service | 8290 | ✅ Available | Event logging |
| Notification | 8570 | ✅ Available | SMS/Email/Push |

---

## Bot Services Layer Analysis

### **Existing Bot Services (6 total)**

#### 1. **Bot-Ingress Service** (Frontend gateway)
**Current Role:** Entry point for external messages  
**Location:** `services/frontend/bot-services/bot-ingress-service/`

**Integration Points:**
- ✅ Already calls ICE for hydration (Phase 4)
- Needs: Configure ICE endpoint to port 8100
- Needs: Use service tokens from hydration response
- Needs: Parse session_state and expected_action

**Changes Required:**
```python
# bot-ingress-service/app/worker.py
1. Update ICE_URL to http://ice-service:8100
2. Parse hydration response:
   - Extract service_token for downstream calls
   - Store session_state in context
   - Use expected_action for routing
3. Route to appropriate bot based on session_state:
   - chat → Default Bot (menu, product browsing)
   - cart → Cart Handler (add/remove items)
   - order → Order Handler (address, delivery)
   - payment → Payment Handler (method selection)
   - delivery → Delivery Handler (tracking)
```

**Priority:** HIGH (entry point)

---

#### 2. **Default-Bot Service** (Rules-driven)
**Current Role:** Menu generation, product browsing  
**Location:** `services/frontend/bot-services/default-bot-service/`

**Integration Points:**
- Expected state: CHAT
- Should generate menus based on expected_action
- Should handle product selection → transition to CART

**Changes Required:**
```python
# default-bot-service/app/intent_handler.py
1. Accept hydration blob in request context
2. If state=chat and action=show_menu:
   - Generate product menu from catalog_context.products
   - Format variants with stock levels
   - Include product IDs for selection
3. On product selection:
   - Call bot-session PATCH /session/{id}/context
   - Store selected_items in state_context
   - Request state transition to CART
4. Pass service_token from metadata for auth
```

**Port:** 8001 (recommended, currently unassigned)  
**Priority:** HIGH (primary user interaction)

---

#### 3. **Intent-Service** (LLM-powered)
**Current Role:** Natural language understanding (Gemini)  
**Location:** `services/frontend/bot-services/bot-intent-service/`

**Integration Points:**
- Processes user input
- Returns intent + entities
- Should use session context for accuracy

**Changes Required:**
```python
# bot-intent-service/app/gemini_processor.py
1. Include session_state in LLM context:
   - "User is in {state} state, expecting {action}"
   - Pass state_context to LLM for better understanding
2. Intent responses should indicate state transitions
3. Use service_token for bot-session calls
```

**Port:** 8002 (recommended)  
**Priority:** MEDIUM (enhances interaction quality)

---

#### 4. **Custom-Bot Service** (Node-based engine)
**Current Role:** Custom workflow execution  
**Location:** `services/frontend/bot-services/custom-bot-service/`

**Integration Points:**
- Executes custom business flows
- Should respect session states
- May trigger state transitions

**Changes Required:**
```python
# custom-bot-service/app/node_engine.py
1. Initialize with hydration context
2. Nodes can call state transition endpoint:
   - POST /session/{id}/transition
   - Pass required context for next state
3. Access service_token from metadata
4. Verify states are allowed transitions
```

**Port:** 8003 (recommended)  
**Priority:** MEDIUM (advanced flows)

---

#### 5. **Bot-Reply Service** (Response formatting)
**Current Role:** Format responses for channels  
**Location:** `services/frontend/bot-services/bot-reply-service/`

**Integration Points:**
- Receives bot output (text, options, etc.)
- Formats for SMS/WhatsApp/HTTP
- Should include state hints

**Changes Required:**
```python
# bot-reply-service/app/formatters.py
1. Include current_state in response metadata
2. Add state-appropriate CTA buttons:
   - chat: "Select product" → option list
   - cart: "Proceed to order" → button
   - order: "Confirm address" → form
   - payment: "Select method" → payment options
   - delivery: "Track package" → link
3. Pass service_token for async updates
```

**Port:** 8004 (recommended)  
**Priority:** MEDIUM (UX improvement)

---

#### 6. **Outbound Service** (Channel delivery)
**Current Role:** Send to SMS/WhatsApp/HTTP  
**Location:** `services/frontend/bot-services/outbound-service/`

**Integration Points:**
- Final delivery to channels
- May receive delivery callbacks
- Should log state transitions

**Changes Required:**
```python
# outbound-service/app/channel_sender.py
1. On message delivery:
   - Log delivery_status in event stream
2. On callback (delivery/read):
   - Emit to audit service
   - Update session event record
3. Webhook handlers for payment/delivery updates:
   - Receive external callbacks
   - Call bot-session transition endpoint
   - Trigger state progression
```

**Port:** 8005 (recommended)  
**Priority:** MEDIUM (channel integration)

---

## State Progression Flow

```
User Message → Ingress (Port ?) 
↓
Hydrate via ICE (Port 8100)
├─ Get session_state (e.g., "chat")
├─ Get expected_action (e.g., "show_menu")
├─ Get catalog_context (products)
└─ Get service_token (for auth)
↓
Route to appropriate bot based on state:
├─ CHAT → Default-Bot (8001)
│  ├─ Generate menu
│  ├─ User selects product
│  ├─ Call bot-session PATCH /context (save selected_items)
│  └─ Call bot-session POST /transition (to CART)
│
├─ CART → Cart-Handler
│  ├─ Show cart summary
│  ├─ User confirms
│  ├─ Call bot-session PATCH /context (save cart_summary)
│  └─ Call bot-session POST /transition (to ORDER)
│
├─ ORDER → Order-Handler
│  ├─ Collect address, delivery method
│  ├─ Call bot-session PATCH /context
│  └─ Call bot-session POST /transition (to PAYMENT)
│
├─ PAYMENT → Payment-Handler (Port 8590)
│  ├─ Initiate payment
│  ├─ Wait for webhook callback
│  ├─ On success: POST /transition (to DELIVERY)
│  └─ Store transaction_id in context
│
└─ DELIVERY → Delivery-Handler (Port 8560)
   ├─ Show tracking info
   ├─ Wait for delivery confirmation
   └─ POST /transition (to CLOSED)
```

---

## Integration Sequence

### Phase 1: Port Assignment & Configuration (Week 1)
```
- Assign unique ports to each bot service
- Update docker-compose.yml with port bindings
- Configure environment variables
- Add service discovery entries
```

**Services to Configure:**
- bot-ingress-service: Port 8001
- default-bot-service: Port 8002
- bot-intent-service: Port 8003
- custom-bot-service: Port 8004
- bot-reply-service: Port 8005
- outbound-service: Port 8006

---

### Phase 2: ICE Integration Points (Week 1-2)
```
- Bot-Ingress calls ICE /hydrate for all messages
- Parse hydration response structure
- Extract service_token for downstream calls
- Store session_state and expected_action
```

---

### Phase 3: State Transition Integration (Week 2)
```
- Default-Bot implements product selection → CART transition
- Cart service implements ADD/REMOVE → cart updates
- Payment integration for payment callbacks
- Delivery tracking integration
```

---

### Phase 4: End-to-End Testing (Week 3)
```
- Test complete chat → cart → order → payment → delivery → closed
- Verify state transitions are respected
- Verify context persistence per cycle
- Verify affiliate attribution
```

---

## Configuration Changes Needed

### docker-compose.yml Updates
```yaml
bot-ingress:
  ports:
    - "8001:8000"
  environment:
    ICE_SERVICE_URL: http://ice-service:8100
    BOT_SESSION_URL: http://bot-session:8540
    
default-bot:
  ports:
    - "8002:8000"
  environment:
    ICE_SERVICE_URL: http://ice-service:8100
    BOT_SESSION_URL: http://bot-session:8540
    
# ... repeat for other services
```

---

## Key Integration Points

### ✅ Already Available
- ICE Hydration (8100) - Session state + context
- Bot-Session (8540) - State transitions + cycles
- MSME (8500) - User/business/tokens
- Service Token Auth - JWT in headers

### 🔄 Need to Implement
1. **Bot-Ingress**: Parse hydration, route by state
2. **Default-Bot**: Menu generation, product selection
3. **Cart Handler**: Add/remove items, cart summary
4. **Order Handler**: Address collection, delivery method
5. **Payment Handler**: Payment initiation, webhook handling
6. **Delivery Handler**: Tracking, confirmation

### 📝 Need to Add
1. Environment variable templates for all services
2. Service discovery/routing by state
3. Webhook handlers for payment/delivery
4. Error handling for failed transitions
5. Logging/audit for all state changes

---

## Risk Mitigation

### Compatibility Risks
- Old bot services may not support new state-driven architecture
- Gradual rollout: Start with Ingress → Default → others

### State Management Risks  
- Ensure atomic transitions (database locks)
- Idempotent state transition calls
- Rollback plan if transition fails

### Service Discovery
- All services need to know ICE + Bot-Session URLs
- Use environment variables + service discovery

---

## Summary

**Current:** ICE Service fully operational  
**Next:** Integrate Ingress + Bot services with hydration  
**Timeline:** 2-3 weeks for full integration  
**Testing:** End-to-end flow validation required  

**Quick Win:** Bot-Ingress integration (1 week)
