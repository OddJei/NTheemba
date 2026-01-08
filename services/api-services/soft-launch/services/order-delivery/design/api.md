# API (Soft Launch)

## Orders
### POST /orders/create
Creates an order in `pending_payment`.

Request (example):
```json
{
  "session_id": "sess_123",
  "user_phone": "+27...",
  "user_id": null,
  "business_id": "...",
  "delivery_method": "pickup",
  "total_amount": 12500,
  "currency": "ZAR",
  "metadata": {"cart_id": "..."}
}
```

### POST /orders/{order_id}/mark_paid
Marks order `paid` and emits `order_paid`.

## Delivery
### POST /delivery/initiate/{order_id}
Generates a delivery code for a paid order (or returns existing delivery if already initiated).
Emits `delivery_code_generated`.

### POST /delivery/{delivery_id}/confirm
Request:
```json
{
  "delivery_code": "123456",
  "confirmed_by": "msme_staff_or_bot"
}
```
Confirms delivery, marks order `delivered`, emits `delivery_confirmed` + `order_delivered`.
