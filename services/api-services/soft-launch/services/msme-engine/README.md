# MSME Engine (Soft Launch)

Implements the fused **Auth Service** + **Business Service** soft-launch design.

## Run

```bash
pip install -r requirements.txt
uvicorn src.app.main:app --reload --port 8501
```

## Headers

- `X-Correlation-Id` (optional): echoed back in responses
- `X-Idempotency-Key` (optional): idempotent writes for POST/PUT/DELETE

## Core Routes

### Auth
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`
- `GET /auth/phone/{user_phone}`
- `PUT /auth/user/{user_id}`
- `DELETE /auth/user/{user_id}`

### Business
- `POST /business/register`
- `GET /business/{id}`
- `PUT /business/{id}`
- `DELETE /business/{id}`
- `POST /business/{id}/subscribe`
- `GET /business/{id}/subscription`
- `GET /business/{id}/metadata`
- `GET /business/phone/{phone_number}`
- `POST /business/reindex`

### Payment Events (for subscription activation)
- `POST /events/payment_success`
- `POST /events/payment_failed`
- `GET /events/business/{business_id}`
