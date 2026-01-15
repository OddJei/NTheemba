# Service Run Commands (Soft Launch)

Quick reference to start each service locally. Default host is 127.0.0.1 unless noted.

> Notes: use PowerShell. Create/activate a venv where shown. Node service uses npm.

## Affiliate Engine
```
cd services/affiliate-engine
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn src.app.main:app --reload --port 8510 --host 127.0.0.1
```
Notes: emits audit events; optional outbox dispatcher: `python -m src.app.outbox_dispatcher` (needs EVENT_SINK_URL).

## MSME Engine
```
cd services/msme-engine
pip install -r requirements.txt
uvicorn src.app.main:app --reload --port 8500 --host 127.0.0.1
```

## Catalog + Inventory
```
cd services/catalog-inventory
pip install -r requirements.txt
uvicorn src.app.main:app --reload --port 8520 --host 127.0.0.1
```
Notes: optional outbox dispatcher: `python -m src.app.outbox_dispatcher` (needs EVENT_SINK_URL).

## Cart
```
cd services/cart
pip install -r requirements.txt
uvicorn src.app.main:app --reload --port 8530 --host 127.0.0.1
```
Notes: optional outbox dispatcher: `python -m src.app.outbox_dispatcher` (needs EVENT_SINK_URL).

## Order + Delivery
```
cd services/order-delivery
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PORT="8560"
python -m uvicorn src.app.main:app --host 127.0.0.1 --port $env:PORT
```
Notes: optional outbox dispatcher: `python -m src.app.outbox_dispatcher`.

## Payment + Revenue
```
cd services/payment-revenue
$env:DATABASE_URL="sqlite+aiosqlite:///./payment_revenue.db"
$env:MSME_BASE_URL="http://127.0.0.1:8500"
$env:ORDER_DELIVERY_BASE_URL="http://127.0.0.1:8560"
$env:AFFILIATE_ENGINE_BASE_URL="http://127.0.0.1:8510"
python -m uvicorn src.app.main:app --reload --port 8590
```

## Bot-Session
```
cd services/bot-session
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
setx DATABASE_URL "sqlite:///./dev.db"
uvicorn src.app.main:app --reload --port 8000
```

## Notification (Node)
```
cd services/notification
npm ci
npm start
```

## Audit Service
```
cd services/audit-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8290
```
Notes: requires Postgres env vars (PG_USER, PG_PASSWORD, PG_DB, PG_HOST). Optionally run Alembic migrations.
