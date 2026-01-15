# Payment + Revenue Service (Soft Launch)

Computes settlement splits (MSME net, platform fee, affiliate commission) using **integer minor units** and persists a settlement ledger.

## Policy
- MSME transaction fee is fetched from MSME Engine entitlements:
  - Free: 7% (0.07)
  - Paid: 5% (0.05)
- Affiliate commission is configured as a share of the platform fee (defaults to 0%).

## Run
```powershell
$env:DATABASE_URL = "sqlite+aiosqlite:///./payment_revenue.db"
$env:MSME_BASE_URL = "http://127.0.0.1:8500"
$env:ORDER_DELIVERY_BASE_URL = "http://127.0.0.1:8560"
$env:AFFILIATE_ENGINE_BASE_URL = "http://127.0.0.1:8510"
python -m uvicorn src.app.main:app --reload --port 8590
```

## Main endpoint
- `POST /events/payment-success`

Payload expects:
- `payment_id`, `order_id`, `business_id`, `amount_minor`, `currency`

The service will:
1. Fetch MSME entitlements to get fee percent.
2. Compute splits (platform fee, affiliate commission, MSME net).
3. Store settlement in DB (idempotent by `order_id`).
4. Call Order+Delivery to mark order paid.
5. Emit affiliate-engine `payment_success` event.
