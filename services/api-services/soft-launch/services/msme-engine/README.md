# MSME Engine (Soft Launch)

Implements the fused **Auth Service** + **Business Service** soft-launch design.

## Run

```bash
pip install -r requirements.txt
uvicorn src.app.main:app --reload --port 8500 --host 127.0.0.1
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

#### POST /business/register — Notes

- Purpose: register a new business. The request must include exactly one of:
 	- `owner` — an object with `username`, `email`, `phone`, `password` (service will create a new user), OR
 	- `owner_user_id` — string id of an existing `User` to link as the business owner.
- Validation / errors:
 	- 400 `owner_required` — both or neither of `owner`/`owner_user_id` provided.
 	- 409 `owner_user_conflict` — attempting to create an `owner` with a username/email that already exists.
 	- 422 — Pydantic validation errors for malformed JSON or invalid fields.
 	- 500 — unexpected server errors (recently seen when `msme_events.event_id` exceeded the DB column length; migration added to increase length).
- Idempotency: honor `X-Idempotency-Key` for safe retries.
- Side-effects:
 	- Creates `User` (if `owner` provided) and `Business` records, links owner to business, generates an `msme_code`, records a local lifecycle event and emits an audit event.

Example payload (create new owner):

```json
{
 "owner": {
  "username": "acme_owner_01",
  "email": "owner+acme@example.com",
  "phone": "+260971000001",
  "password": "S3cureP@ssw0rd!"
 },
 "name": "Acme Traders",
 "location": "Lusaka",
 "category": "Retail",
 "logo_url": "https://example.com/logos/acme.png",
 "affiliate_code": "ACME2026",
 "referred_by_msme_code": null,
 "subscription_plan": "free",
 "delivery_locations": {"zones": ["Lusaka Central", "Lusaka North"]},
 "tags": ["groceries", "local"]
}
```

Example payload (link existing user):

```json
{
 "owner_user_id": "c301a1bd-7506-4229-9603-00d4474087c5",
 "name": "Acme Traders",
 "location": "Lusaka"
}
```

Typical responses:

- 201: business created (body: `BusinessRegisterOut` with `msme_code`).
- 409: `owner_user_conflict` when owner creation collides with existing user.

### Payment Events (for subscription activation)

- `POST /events/payment_success`
- `POST /events/payment_failed`
- `GET /events/business/{business_id}`
