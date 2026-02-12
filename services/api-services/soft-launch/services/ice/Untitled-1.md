Alright James — here’s the **entire canonical end‑to‑end system map**, bringing *everything* up together: ingress, ICE, bot‑session, cart/catalog/order/delivery, payment‑revenue, notification, outbound, affiliate engine, MSME engine, and audit service. Nothing left out.

---

## 🌐 Ingress Workflow
1. **Bot‑Ingress**
   - Consumes from `incoming:message`.
   - Validates payload (`request_id`, `to`, `from`, `meta.platform`).
   - Enforces **idempotence**.
   - Forwards validated payload to ICE.

2. **ICE Hydration**
   - Saves incoming message.
   - Hydrates using `to`, `from`, `platform`, `user_text`.
   - Detects affiliate token (`ace:` prefix + `[[AFFLINK]]`).
   - Extracts token, affiliate_id, product if present.

3. **Business Resolution**
   - Resolve `/business/phone/{phone_number}` via MSME Engine.
   - Collect business + owner details.
   - Cache in Redis (`businessdetails:{business_phone}`) with long TTL.
   - ICE checks cache/db before calling MSME Engine.

4. **Affiliate Resolution**
   - If token present, resolve affiliate details via Affiliate Engine.
   - Collect affiliate_id, product linked to token.

5. **Bot‑Session Resolution**
   - Resolve bot type + bot_id from business_id.
   - If none, create new bot.
   - Resolve session_id from `from_phone` + `platform`.
   - If none, create new session.
   - Resolve cycle_id from sessions table.
   - If affiliate_id present, always create new cycle with affiliate_id.
   - Collect context snapshot + cycle_state.

6. **Session Data**
   - Persist cycle_id, session_id, intent flag (ON by default), stage=cycle_state.
   - If affiliate prefix detected, intent flag OFF → map to cart intent canonical id.
   - Add product slot details (product_id, name, price).
   - Parse context snapshot if cycle is new.

7. **Customer Details**
   - Resolve `/auth/phone/{from_phone}`.
   - Parse user details blob keyed by `from_phone`.

8. **Cart & Order Check**
   - Check CartService for cart with cycle_id not checked out.
   - Cache cart snapshot if found.
   - Check OrderDeliveryService for unconfirmed delivery orders.
   - Cache order snapshot if found.

9. **Product Snapshot**
   - Resolve product snapshot via business_id.
   - Cache with long TTL.

10. **OOB Store**
   - Redis hash keyed `oob:{session_id}`.
   - Stores hydrated blobs, cart object, meta contexts (order, payment, refund, diagnostics).
   - Updated via ICE hydrate and runtime handlers using optimistic CAS.

11. **Persistence**
   - Map all collected data into blob with TTL.
   - Persist to PostgreSQL for longevity.

12. **Ingress Completion**
   - Parse blobs into payload meta (enrichment).
   - Publish enriched payload to `bot:lane:{bot_type}`.

---

## 🤖 Custom Bot Service Workflow
- Consumes payload from bot lane.
- Validates payload + idempotence.
- Reads `need_intent` flag (ON by default).
- Builds strict multi‑intent context (payload mapper, product snapshots, cart/order objects, session data, OOB).
- Sends context to Gemini → validates response.
- Multi‑intent executor runs canonical stage order: **chat → cart → order → payment → delivery**.
- Cache‑first (OOB), authoritative ICE calls if cache missing/stale.

---

## 🛒 Cart Service Workflow
- Create cart → new cart for session/user.  
- Add items → product/variant info + quantity.  
- Update items → quantity/details updated.  
- Remove items → by item ID.  
- Fetch cart → by session/user phone.  
- Checkout → finalized, handed off to order creation.  

---

## 📦 Catalog + Inventory Workflow
- Catalog setup → categories/products created/updated.  
- Variants → sizes, colors, etc.  
- Business catalog → list all products under business.  
- Media upload → product images/files stored (Nextcloud).  
- Inventory update → stock per variant.  
- Inventory lookup → current stock retrieved.  
- Reindex (optional) → rebuild indexes after bulk updates.  

---

## 📑 Order + Delivery Workflow
- Create order → from cart (user + business + items + delivery method).  
- Initiate payment → order moves to pending payment.  
- Mark paid → payment service callback.  
- Initiate delivery → delivery code generated + sent.  
- Confirm delivery → customer provides code, order marked complete.  
- Affiliate hook → if affiliate_id present, event sent to Affiliate Engine.  

---

## 💳 Payment‑Revenue Workflow
- Payment success event triggered by provider callback or order flow.  
- Fetch MSME fee rules.  
- Calculate split: platform fee, affiliate commission, MSME net.  
- Settlement stored idempotently by order ID.  
- Mark order paid in Order‑Delivery.  
- Emit payment success event to Affiliate Engine.  

---

## 📢 Notification Service Workflow
- Health check → endpoint for liveness.  
- Send notification → services call with channel (`whatsapp`, `email`, `in_app`).  
- Routing:  
  - **WhatsApp** → routed through WhatsApp provider.  
  - **Email** → routed through SMTP.  
  - **In_app** → stored internally (no external delivery).  
- Storage → every notification saved with status (`sent` or `failed`).  
- Query → fetch by ID or list all notifications for a user.  

---

## 📤 Outbound Workflow
- Custom bot service publishes enriched payload to `outbound:request`.  
- Outbound service consumes request.  
- Strips enrichment → keeps only `to`, `from`, `reply_text`, `meta.platform`, `bot_id`.  
- Calls ICE to persist outbound message (cycle snapshot + OOB + session history).  
- Publishes cleaned payload to `outbound:{platform}`.  
- Platform‑specific outbound workers deliver message.  

---

## 🔄 Affiliate Engine Automations
- Affiliate creation → created in Affiliate Engine with `user_id` from MSME Engine.  
- Link creation → affiliate generates campaign link.  
- Link resolution → user click → short‑lived token.  
- Token resolution → product + affiliate context bound to bot session.  
- Click tracking → every link click recorded.  
- Conversion attribution → orders linked to affiliate_id.  
- Payment success → sale event recorded.  
- Delivery confirmation → sale marked delivered → affiliate delivered event.  
- Metrics computation → GMV, unique buyers, MSME referrals, conversion quality.  
- Pool calculation → weighted scores (0.5 GMV, 0.2 buyers, 0.2 referrals, 0.1 conversion quality).  
- Payout allocation → affiliates ranked by score, payouts distributed proportionally.  
- Dashboards → affiliates + admins view earnings, metrics, allocations.  

---

## 🏢 MSME Engine Workflows
- Authentication / access tokens → bearer tokens with claims.  
- User verification (phone) → identity, role, business affiliation, status.  
- Business profile & entitlements → metadata + entitlement flags.  
- Fee/entitlement lookup → fee percentages, commission rules, pricing tiers.  
- Product/business entitlement validation → accept/deny with reasons.  
- Service‑to‑service identity verification → validate service tokens.  
- Business onboarding & entitlement changes → create/modify records, assign entitlements.  
- Short‑lived tokens → single‑use for affiliate link resolution or handoffs.  
- Audit + notifications hooks → emit events on state changes.  
- Health & metadata discovery → endpoints for base URLs, contact numbers, flags.  

---

## 📜 Audit Service Workflows
- Ingest events → structured JSON with event_id, correlation_id.  
- Local persistence + indexing → DB/append‑only store.  
- Outbox/forwarder → dispatch to SIEM, data lake, Kafka, remote API.  
- Real‑time streaming → SSE/websocket for live monitoring.  
- Query & retrieval → filter by service, actor, event_type, time, correlation_id.  
- Alerting & notifications → detect high‑severity events, trigger alerts.  
- Retention & archival → hot store + long‑term storage.  
- Security & access control → trusted service tokens for write, admin scopes for read.  
- Audit enrichment → add metadata (IP, user info, business name).  
- Health & observability → `/health`, `/metrics`, latency, queue depth, retention stats.  

---

## 📝 Canonical End‑to‑End Summary
- **Ingress** → Bot‑Ingress → ICE hydration → MSME Engine (business/user/entitlements) → Affiliate Engine (token resolution) → Bot‑Session setup → OOB persistence → PostgreSQL.  
- **Bot Lane** → Custom bot service → validate payload + idempotence → build context → Gemini.  
- **Executor** → Canonical stage order (chat → cart → order → payment → delivery).  
- **Cart/Catalog/Inventory/Order/Delivery** → authoritative ICE calls, snapshots cached in OOB.  
- **Payment‑Revenue** → fee rules, split calculation, settlement ledger, mark order paid, affiliate event.  
- **Notification Service** → WhatsApp/email/in_app routing, storage, query.  
- **Outbound** → strip enrichment → ICE persist → publish to outbound:{platform}.  
- **Affiliate Engine** → creation tied to MSME user_id, link lifecycle, tracking, attribution, metrics, pool weighting, payouts.  
- **Audit Service** → ingest, persistence, forwarding