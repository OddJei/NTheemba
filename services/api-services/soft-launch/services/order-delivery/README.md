# Order + Delivery Service (Soft Launch)

This service is a fused **Order + Delivery** service for soft-launch. It owns:
- Order lifecycle basics (create, status updates)
- Delivery-code handover flow (generate code after payment, confirm delivery via code)
- Outbox events for notifications/audit integration

## Ports
- Suggested default: **8560**

## Run locally
```powershell
cd c:\Users\SMART PC\Documents\NTheemba\services\api-services\soft-launch\services\order-delivery
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PORT = "8560"
python -m uvicorn src.app.main:app --host 127.0.0.1 --port $env:PORT
```

## Affiliate Engine integration

If `metadata.affiliate_code` is present on `POST /orders/create`, the service will enqueue an `order_created` outbox event that can be forwarded to Affiliate Engine (`POST /events/order-created`) for attribution.

Config:
- `AFFILIATE_ENGINE_BASE_URL` (default `http://127.0.0.1:8510`)
- `AFFILIATE_ENGINE_TIMEOUT_SECONDS` (default `3.0`)

Optional outbox dispatcher (retries and marks events processed):
```powershell
python -m src.app.outbox_dispatcher
```

## Endpoints
- `GET /health`
- `GET /metrics`

Orders:
- `POST /orders/create`
- `GET /orders/{order_id}`
- `POST /orders/{order_id}/initiate_payment`
- `POST /orders/{order_id}/mark_paid`

Delivery:
- `POST /delivery/initiate/{order_id}`
- `GET /delivery/{delivery_id}`
- `GET /delivery/order/{order_id}`
- `POST /delivery/{delivery_id}/confirm`
- `GET /delivery/user/{user_phone}`

## Payment initiation flow
1) Create an order: `POST /orders/create`
2) Initiate payment: `POST /orders/{order_id}/initiate_payment`
	- Body: `phoneNumber`, `provider`, `currency`
	- Calls payment-revenue `/pawapay/deposits/initiate`
3) payment-revenue receives pawaPay callback and calls:
	- `POST /orders/{order_id}/mark_paid`

## Auth notes
- All endpoints require a Bearer token from MSME Engine **except**:
  - `GET /health`, `GET /metrics`
  - `POST /orders/{order_id}/mark_paid` (service-to-service callback)

## Notes
- Delivery codes are generated server-side and returned once from `/delivery/initiate/{order_id}`.
- The DB stores only a **salted hash** of the code (not the cleartext code).
