# Soft Launch Integration Points (Service-Level)

## Hybrid plugin model (recommended)

- Bot requests should hit an **ICE/orchestrator** layer that calls **automation plugins**.
- Automation plugins reuse **service adapters** (Cart/Order/Payment/Delivery/Notification/etc.).
- Adapters call services through the shared transport plugin client:
   - see `contracts/transport-plugins.md` and `contracts/python/soft_launch_client/`.

## Common transport
- Sync: HTTP APIs between services (simple for soft launch)
- Async: event names below (can be Redis pub/sub / queue later)

## Core IDs passed between services
- session_id (from Bot-Session)
- business_id (MSME)
- user_phone (customer)
- cart_id, order_id, payment_id, delivery_id

## Canonical flow (happy path)
1) Bot-Session -> Cart
   - POST /cart/create (session_id, user_phone, business_id)
   - POST /cart/{id}/add
2) Cart -> Order
   - POST /cart/{id}/checkout (returns checkout payload)
   - POST /order/create (business_id, user_phone, items, delivery_location, metadata{session_id, affiliate_code?})
3) Order -> Payment+Revenue
   - POST /payment/initiate (amount, user_id/user_phone, business_id, metadata{order_id})
   - POST /payment/{id}/verify
4) Payment+Revenue -> (events) -> Order/Delivery/Notification
   - payment_success -> Order marks paid; Delivery generates code; Notification sends MSME message
5) Delivery -> Order + Payment+Revenue
   - delivery_confirmed -> Order fulfilled/delivered; Payment+Revenue sets payout_ready

## Affiliate attribution points
- If affiliate_code/link present at order create:
  - Order stores affiliate_id/code in metadata
  - Payment+Revenue calculates earnings on payment_success
