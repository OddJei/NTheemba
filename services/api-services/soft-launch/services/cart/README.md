Cart Service (Soft Launch)

Run

```bash
pip install -r requirements.txt
uvicorn src.app.main:app --reload --port 8530 --host 127.0.0.1
```

Endpoints

- `GET /health`
- `POST /cart/create`
- `POST /cart/{id}/add`
- `PUT /cart/{id}/update`
- `DELETE /cart/{id}/remove/{item_id}`
- `GET /cart/session/{session_id}`
- `GET /cart/user/{user_phone}`
- `POST /cart/{id}/checkout`

Headers

- `X-Correlation-Id` optional, echoed back
- `X-Idempotency-Key` optional for write operations

Migrations (Alembic)

```bash
# autogenerate new revision
alembic revision --autogenerate -m "change"

# apply migrations
alembic upgrade head
```

Outbox dispatcher

```bash
# requires EVENT_SINK_URL
python -m src.app.outbox_dispatcher
```
