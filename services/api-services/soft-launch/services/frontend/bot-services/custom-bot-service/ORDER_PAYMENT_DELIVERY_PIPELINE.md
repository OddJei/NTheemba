# Order -> Payment -> Delivery Pipeline

## Existing Functions/Classes (Entry Points)

- ICE client: custom-bot-service/app/ice_client.py
  - IceClient.create_session()
  - IceClient.update_stage()
  - IceClient.hydrate()
  - IceClient.create_order()
  - IceClient.trigger_payment()
  - IceClient.get_business_by_phone()
  - IceClient.price_cart()
  - IceClient.check_stock()
- Runtime engine: custom-bot-service/app/runtime_engine.py
  - process_event()
  - ensure_session_and_cycle()
  - resolve_stage_via_ice()
  - confirm_cart_and_initiate_order()
  - validate_and_review_order()
  - transition_to_payment()
  - collect_payment_inputs_one_turn()
  - validate_payment_inputs()
  - transition_to_delivery()
- OOB store: custom-bot-service/app/oob_store.py
  - OOBStore.get_oob()
  - OOBStore.create_default_if_missing()
  - OOBStore.cas_update()
- Bot-session (authoritative lifecycle): services/bot-session/src/app/main.py
  - _build_cycle_context() (context alignment)
  - /admin/session/{session_id}/full (cycle metadata)
  - SessionStateCycle model in services/bot-session/src/app/models.py
- MSME engine (delivery locations on business): services/msme-engine/src/app/main.py + schemas.py
  - Business.delivery_locations field in schemas
- Affiliate engine: services/affiliate-engine/src/app/main.py
  - Session cycle event handlers and affiliate attribution pipelines
- Catalog + Inventory: services/catalog-inventory/src/app/main.py
  - /catalog/*, /inventory/* endpoints
  - Nextcloud client: services/catalog-inventory/src/app/nextcloud_client.py
- Cart service: services/cart/src/app/main.py
  - /cart/create, /cart/{cart_id}/add, /cart/active
- Order + Delivery: services/order-delivery/src/app/main.py
  - /orders/*, /deliveries/*, /payments/*, outbox dispatch
- Audit service: services/audit-service/main.py
  - /audit/log, /audit/{audit_id}
- Notification service: services/notification/app.js
  - /notification/send, /notify/email, /notify/sms
- Nextcloud: services/catalog-inventory/src/app/nextcloud_client.py
  - NextcloudClient.upload_product_media()
- Payment + Revenue: services/payment-revenue/src/app/main.py
  - /pawapay/deposits/initiate, /callbacks/pawapay/*, payout endpoints
- Delivery service: services/delivery/ (no src entry point present in repo)

## End-to-End Flow (Strict)

### 1) Order stage (confirm_cart intent)

- Handler: confirm_cart_and_initiate_order()
- ICE update_stage:
  - new_stage = "order"
  - context includes cart_items + checkout flag
- Follow-up: validate_and_review_order() auto-validates items, checks stock, calculates totals, reviews order
- Bot reply is direct Gemini (persona NTheemba) with light Bemba/Nyanja mix

### 2) Payment stage (after order confirmation)

- Handler: confirm_order_gate() -> transition_to_payment()
- ICE update_stage:
  - new_stage = "payment"
  - context includes order_id, cart_items, total_price
- Input collection (single turn): collect_payment_inputs_one_turn()
  - Mobile money phone must start with 260
  - Delivery option: pickup or delivery
  - Delivery location: town + exact address
- Validation: validate_payment_inputs()
  - Re-asks only invalid fields
- Once valid: reply asks for CONFIRM PAYMENT

### 3) Delivery stage (after CONFIRM PAYMENT)

- Handler: confirm_payment_gate() -> transition_to_delivery()
- ICE update_stage:
  - new_stage = "delivery"
  - context includes order_id, payment_phone, delivery_option, delivery_location, total_price
- Bot reply: order id + instruction to enter PIN on the mobile money number

### 4) Refund stage (initiate_refund)

- Intents: `refund.request`, `refund.collect_reason`.
- Handler: `initiate_refund()` implemented in `app/handlers/initiate_refund.py`.
- Expected behavior:
  - If user expresses a refund intent without a reason, the bot asks: "Please tell us the reason for the refund request."
  - When a reason is provided in a subsequent message (or the same turn), `initiate_refund` calls ICE to record the refund request and notifies admin/staff to investigate.
  - The bot responds with a direct Gemini reply (persona `NTheemba`) confirming the refund was logged and that admin will investigate.
- ICE endpoints used:
  - `POST /ice/refund/request` — records refund request and returns `refund_id`/`status`.
  - `POST /ice/admin/notify` — ask ICE to notify admin/staff about the refund for investigation.
- OOB meta writes:
  - `meta.refund_request_id` — refund id from ICE (if present)
  - `meta.refund_status` — recorded status (e.g. `requested`)
  - `meta.refund_reason` — user-provided reason
  - `last_node_executed` updated to `initiate_refund`
- Side-effects and observability:
  - Handler logs structured diagnostics on failure (`refund_request_failed`, `order_id_missing`).
  - Admin notification is best-effort (failure does not block recording the refund request).
- Tests to add/adjust:
  - Unit tests for `initiate_refund` covering missing order_id, ICE failures, successful flow and OOB updates.
  - Integration test to simulate `refund.request` -> `refund.collect_reason` -> ICE calls and admin notify.

## Context Snapshot (Bot-session Alignment)

- build_payment_context() assembles:
  - user_state, diagnostics
  - order_id, cart_items, total_price
  - payment_phone, delivery_option, delivery_location
  - payment_method = "mobile_money"
- confirm_cart_and_initiate_order() persists order_context into OOB meta
- payment collection persists payment_context into OOB meta

## Backend Services Involved

- ICE service
  - /ice/session/create
  - /ice/session/update_stage
  - /ice/hydrate
- Bot-session service
  - SessionStateCycle records and session state updates
  - Context snapshots via _build_cycle_context
- OOB store (Redis CAS updates)
  - meta.order_context, meta.payment_context, meta.payment_phone, meta.delivery_location
- MSME engine
  - Business delivery locations for town validation

## Unit Tests Added

- tests/test_payment_validation.py
  - Phone validation (starts with 260)
  - Delivery option validation (pickup/delivery)
  - Delivery town/address validation
  - Context snapshot schema

## Integration Test Added

- tests/test_pipeline_end_to_end.py
  - confirm_cart -> order -> payment -> delivery
  - Verifies ICE update_stage calls at each transition
  - Verifies OOB meta updates (order + payment context)
  - Verifies direct Gemini reply for delivery confirmation

## Simulation (Sample Payload Flow)

1) User adds bread to cart

- Input: "Add bread"
- OOB: cart.items = [{"product_id":"p1","product_name":"Bread","quantity":2}]

1) Confirm cart -> order

- Input: "confirm cart"
- ICE update_stage(new_stage="order", context={cart_items, checkout:true})
- Bot: order review with total + CONFIRM ORDER prompt

1) Confirm order -> payment

- Input: "CONFIRM ORDER"
- ICE update_stage(new_stage="payment", context={order_id, cart_items, total_price})
- Bot: request phone + delivery option + location

1) Provide payment details in one turn

- Input: "260977123456 delivery Lusaka Plot 12"
- Validation passes, OOB meta populated
- Bot: "Reply CONFIRM PAYMENT to proceed"

1) Confirm payment -> delivery

- Input: "CONFIRM PAYMENT"
- ICE update_stage(new_stage="delivery", context={order_id, payment_phone, delivery_option, delivery_location, total_price})
- Bot: "Order ord-100 is almost set. Enter your PIN on 260977123456 when prompted. Muli bwanji!"
