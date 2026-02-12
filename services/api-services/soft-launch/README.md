# Soft Launch (Multi-Service Bundle)

This folder packages the **soft launch** workflow as multiple services aligned to the "Automated Pipeline Architecture (Soft Launch Version)".

## Local ports (canonical)

Use these ports for local development (override via each service's `PORT` / `*_BASE_URL` env vars as needed):

| Service | Port | Base URL |
|---|---:|---|
| MSME Engine | 8500 | http://127.0.0.1:8500 |
| Affiliate Engine | 8510 | http://127.0.0.1:8510 |
| Catalog + Inventory | 8520 | http://127.0.0.1:8520 |
| Cart | 8530 | http://127.0.0.1:8530 |
| Order + Delivery | 8560 | http://127.0.0.1:8560 |
| Notification | 8570 | http://127.0.0.1:8570 |
| Payment + Revenue | 8590 | http://127.0.0.1:8590 |

## Common flow walkthrough

- Register user → register business → subscribe & pay: `docs/register-business-subscribe-pay.md`

## Folder layout

- `api-services/soft-launch/services/*` — service stubs with `design/` and `src/` placeholders.
- `api-services/soft-launch/affiliate-engine/` — existing runnable service code (if used).
- `api-services/soft-launch/msme-engine/` — existing runnable service code (if used).
- `api-services/soft-launch/{docs,contracts,infra,scripts}` — bundle-level assets.

## Service mapping (source templates → soft-launch)

### Core services

- Cart → `api-services/cart-service/*design*.txt` → `api-services/soft-launch/services/cart/design/`
- Order → `api-services/order-service/*design*.txt` → `api-services/soft-launch/services/order/design/`
- Bot-Session → `api-services/bot-session-service/*design*.txt` and `api-services/user-bot-session-service/*design*.txt` → `api-services/soft-launch/services/bot-session/design/`
- Notification → `api-services/notification-service/*design*.txt` → `api-services/soft-launch/services/notification/design/`
- Delivery → `api-services/delivery-service/*design*.txt` → `api-services/soft-launch/services/delivery/design/`

- Catalog + Inventory (fused) → `api-services/catalog-inventory-service/*design*.txt` → `api-services/soft-launch/services/catalog-inventory/design/`

### Fused services

- Affiliate Engine (fused) →
  - `api-services/affiliate-service/*design*.txt`
  - `api-services/affiliate-event-service/*design*.txt`
  - `api-services/affiliate-multiplier-service/*design*.txt`
  - `api-services/affiliate-pool-service/*design*.txt`
  - `api-services/auth-service/*design*.txt` (affiliate onboarding/auth)
  → copied into `api-services/soft-launch/services/affiliate-engine/design/`

- MSME Engine (fused) →
  - `api-services/auth-service/*design*.txt` (MSME onboarding/auth)
  - `api-services/business-service/*design*.txt` (MSME business logic)
  → copied into `api-services/soft-launch/services/msme-engine/design/`

- Payment + Revenue (fused) →
  - `api-services/payment-service/*design*.txt`
  - `api-services/revenue-partition-service/*design*.txt`
  - legacy designs from `api-services/lagacy/**/*revenue*|*partition*|*payment*.txt`
  → copied into `api-services/soft-launch/services/payment-revenue/design/`

## Notes

- Legacy templates live under `api-services/lagacy/` (folder name is misspelled). Some soft-launch design folders may rely on those `.txt` files when the main service folder is missing/empty.
- In `api-services/soft-launch/services/*/design/`, copied files are prefixed with their source service name to avoid overwriting `design.txt` collisions.
