# Catalog + Inventory (Soft Launch)

Fused **Catalog + Inventory** implementation for soft launch.

## Run

```bash
pip install -r requirements.txt
uvicorn src.app.main:app --reload --port 8520 --host 127.0.0.1
```

## Headers

- `X-Correlation-Id` (optional): echoed back in responses
- `X-Idempotency-Key` (optional): idempotent writes for POST/PUT/DELETE

## Core Routes

### Health
- `GET /health`

### Catalog
- `POST /catalog/category`
- `GET /catalog/category/{id}`
- `GET /catalog/categories`
- `PUT /catalog/category/{id}`
- `DELETE /catalog/category/{id}`

- `POST /catalog/product`
- `GET /catalog/product/{id}`
- `PUT /catalog/product/{id}`
- `DELETE /catalog/product/{id}`
- `POST /catalog/product/{id}/variant`
- `GET /catalog/business/{id}`

- `POST /catalog/reindex/{business_id}`

### Inventory
- `POST /inventory/update`
- `GET /inventory/{variant_id}`

### Events (outbox)
- `GET /events` (optional debug)
