# Status Mapping (Harmonized)

## Order (order_service.orders.status)
Existing values: pending, confirmed, paid, fulfilled, cancelled

Soft-launch canonical meanings:
- created  -> pending
- confirmed -> confirmed
- paid -> paid
- delivered -> fulfilled   (delivery_confirmed triggers this)
- cancelled -> cancelled

## Delivery (delivery_service.deliveries.status)
- pending -> record created, waiting for payment_success
- code_sent -> delivery_code generated + sent via Notification
- confirmed -> customer code validated; handover completed

## Cart (cart_service.carts.status)
- active -> still adding/removing items
- checked_out -> cart converted to an order
- abandoned -> cleanup job marked it inactive

## Payment (payment_service.transactions.status)
- initiated -> request created
- pending -> gateway awaiting completion
- success -> verified
- failed -> verified failed/expired
