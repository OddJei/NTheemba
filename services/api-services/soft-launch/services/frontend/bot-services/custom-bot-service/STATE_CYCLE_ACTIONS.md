# Custom Bot Service - Session State Cycle Actions

Reference: bot-session `SessionStateCycle` uses `SessionState` stages: chat, cart, order, payment, delivery, closed.

This document defines the actionable handlers per stage for the custom bot runtime.

## Stage: chat
Primary goal: greet, understand intent, browse catalog, and begin building the cart.

Actionable handlers:
- greet_and_suggest → greet user, suggest actions
  - app/handlers/greet_and_suggest.py
- help_text → help menu and guidance
  - app/handlers/help.py
- browse_catalogue_serve_categories → list categories
  - app/handlers/browse_catalogue_serve_categories.py
- browse_catalogue_select_category → select category and list products
  - app/handlers/browse_catalogue_select_category.py
- browse_catalogue_serve_products → list products in a category
  - app/handlers/browse_catalogue_serve_products.py
- browse_catalogue_select_product → select product
  - app/handlers/browse_catalogue_select_product.py
- browse_catalogue_show_product_details → show product details
  - app/handlers/browse_catalogue_show_product_details.py
- inspect_item → inspect a cart/catalog item
  - app/handlers/inspect_item.py
- add_item → add product to cart
  - app/handlers/add_item.py
- remove_item → remove product from cart
  - app/handlers/remove_item.py
- clear_cart → clear cart
  - app/handlers/clear_cart.py
- affiliate_track_click → track affiliate link click
  - app/handlers/affiliate_track_click.py
- affiliate_capture_code → capture affiliate code
  - app/handlers/affiliate_capture_code.py
- fallback_unknown_intent → fallback response
  - app/handlers/fallback_unknown_intent.py

## Stage: cart
Primary goal: review and confirm cart contents before creating an order.

Actionable handlers:
- cart_view → view cart summary
  - app/handlers/cart_view.py
- add_item → add product to cart
  - app/handlers/add_item.py
- remove_item → remove product from cart
  - app/handlers/remove_item.py
- clear_cart → clear cart
  - app/handlers/clear_cart.py
- order_confirm_cart → confirm cart intent (move to order)
  - app/handlers/order_confirm_cart.py
- order_calculate_total → calculate totals
  - app/handlers/order_calculate_total.py
- order_review_order → show order review view
  - app/handlers/order_review_order.py
- fallback_unknown_intent → fallback response
  - app/handlers/fallback_unknown_intent.py

## Stage: order
Primary goal: validate items and create/confirm order draft.

Actionable handlers:
- order_validate_items → validate items in cart
  - app/handlers/order_validate_items.py
- order_check_stock → check stock availability
  - app/handlers/order_check_stock.py
- order_review_order → show order review view
  - app/handlers/order_review_order.py
- confirm_order_gate → confirm order decision
  - app/handlers/confirm_order_gate.py
- fallback_unknown_intent → fallback response
  - app/handlers/fallback_unknown_intent.py

## Stage: payment
Primary goal: confirm payment method and verify payment status.

Actionable handlers:
- confirm_payment_gate → confirm payment method and route
  - app/handlers/confirm_payment_gate.py
- payment_verify_status → check payment status
  - app/handlers/payment_verify_status.py
- fallback_unknown_intent → fallback response
  - app/handlers/fallback_unknown_intent.py

## Stage: delivery
Primary goal: capture delivery method and location.

Actionable handlers:
- fulfillment_choose_method → choose fulfillment method
  - app/handlers/fulfillment_choose_method.py
- fulfillment_select_delivery_option → choose delivery option
  - app/handlers/fulfillment_select_delivery_option.py
- fulfillment_choose_location → select delivery location
  - app/handlers/fulfillment_choose_location.py
- fallback_unknown_intent → fallback response
  - app/handlers/fallback_unknown_intent.py

## Stage: closed
Primary goal: end session and surface a terminal response.

Actionable handlers:
- cancel_flow → cancel and close session
  - app/handlers/cancel.py
- help_text → guidance for closed session
  - app/handlers/help.py
- fallback_unknown_intent → fallback response
  - app/handlers/fallback_unknown_intent.py

## Notes
- Runtime orchestration is in app/runtime_engine.py and determines which handler runs based on parsed intents and current session state.
- `SessionStateCycle` records are created and updated in app/session_cycle.py.
- Keep handler execution idempotent and safe for retries.
