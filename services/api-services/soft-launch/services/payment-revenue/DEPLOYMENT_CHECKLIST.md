# Payment-Revenue Service — Deployment Checklist

## 🔧 Pre-Integration Setup

### 1. Run Migrations on Postgres
```bash
# Set DATABASE_URL to match docker-compose Postgres
export DATABASE_URL='postgresql+asyncpg://postgres:!ladybug!#!@localhost:5432/ntheemba?options=-csearch_path=payment_revenue'

# Or for PowerShell:
$env:DATABASE_URL='postgresql+asyncpg://postgres:!ladybug!%23!@localhost:5432/ntheemba?options=-csearch_path=payment_revenue'

# Run migrations
cd services/payment-revenue
alembic upgrade head
```

### 2. Required Environment Variables

**Critical (must set in production):**
```bash
# pawaPay API credentials
PAWAPAY_API_KEY=your_production_api_key
PAWAPAY_BASE_URL=https://api.pawapay.io/v2  # sandbox: https://api.sandbox.pawapay.io/v2

# Webhook security
PAWAPAY_WEBHOOK_SECRET=your_webhook_secret_here

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db?options=-csearch_path=payment_revenue

# Downstream service URLs (internal)
MSME_BASE_URL=http://msme-engine:8500
AFFILIATE_ENGINE_BASE_URL=http://affiliate-engine:8510
ORDER_DELIVERY_BASE_URL=http://order-delivery:8560
NOTIFICATION_BASE_URL=http://notification:8570

# JWT secret (shared across services)
MSME_JWT_SECRET=your_production_jwt_secret
```

**Optional (tuning):**
```bash
# Reconciliation
PAWAPAY_RECONCILE_ENABLED=true
PAWAPAY_RECONCILE_INTERVAL_SECONDS=300
PAWAPAY_RECONCILE_STALE_SECONDS=900
PAWAPAY_RECONCILE_BATCH_SIZE=50

# Affiliate commission share
AFFILIATE_COMMISSION_SHARE=0.0  # 0.0-1.0 (0=no commission, 1.0=all platform fee)

# HTTP timeouts
HTTP_TIMEOUT_SECONDS=4.0
NOTIFICATION_TIMEOUT_SECONDS=3.0
```

### 3. Remove SQLite DB from Image

**In Dockerfile, ensure you DON'T copy the .db file:**
```dockerfile
# ❌ DON'T DO THIS:
# COPY payment_revenue.db /app/

# ✅ DO THIS instead:
COPY requirements.txt ./
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
```

**Update .dockerignore:**
```
*.db
*.db-journal
__pycache__/
*.pyc
.pytest_cache/
.venv/
```

### 4. Add Migration Step to Container Startup

**Option A: Update docker-compose command:**
```yaml
command: >-
  sh -c "pip install -r requirements.txt && 
         pip install alembic && 
         alembic upgrade head && 
         uvicorn src.app.main:app --host 0.0.0.0 --port 8590"
```

**Option B: Create entrypoint script:**
```bash
#!/bin/sh
# entrypoint.sh
pip install -r requirements.txt
alembic upgrade head
exec uvicorn src.app.main:app --host 0.0.0.0 --port 8590
```

---

## ✅ Integration Verification

### 1. Health Check
```bash
curl http://localhost:8590/health
# Expected: {"status":"ok"}
```

### 2. Test Deposit Flow (End-to-End)
```bash
# Initiate deposit
DEPOSIT_ID=$(uuidgen)
curl -X POST http://localhost:8590/pawapay/deposits/initiate \
  -H "Authorization: Bearer dummy-token" \
  -H "Content-Type: application/json" \
  -d "{\"depositId\":\"$DEPOSIT_ID\",\"amount_minor\":100,\"currency\":\"ZMW\",\"phoneNumber\":\"260760000001\"}"

# Simulate callback (terminal status)
curl -X POST http://localhost:8590/callbacks/pawapay/deposits \
  -H "Content-Type: application/json" \
  -d "{\"depositId\":\"$DEPOSIT_ID\",\"status\":\"COMPLETED\",\"amount\":\"1.00\",\"currency\":\"ZMW\",\"payer\":{\"type\":\"MMO\",\"accountDetails\":{\"phoneNumber\":\"260760000001\",\"provider\":\"MTN_MOMO_ZMB\"}}}"

# Verify outbox rows created
docker-compose exec payment-revenue python -c "
import sqlite3
con=sqlite3.connect('/app/payment_revenue.db')
print('Outbox count:', con.execute('SELECT COUNT(*) FROM outbox').fetchone()[0])
"
```

### 3. Test Outbox Flush
```bash
# Trigger flusher
curl -X POST http://localhost:8590/jobs/outbox/flush \
  -H "Authorization: Bearer dummy-token"

# Check results
# Expected: {"ok":true,"results":{"sent":N,"failed":0}}
```

### 4. Verify Downstream Delivery
```bash
# Check affiliate-engine received event
curl http://localhost:8510/health  # ensure service is up

# Check msme-engine received event
curl http://localhost:8500/health

# Check notification service
curl http://localhost:8570/health
```

---

## 🚀 Production Readiness

### Security
- [ ] Set `PAWAPAY_WEBHOOK_SECRET` and validate in production
- [ ] Use secrets manager (AWS Secrets Manager, Azure Key Vault, etc.) for `PAWAPAY_API_KEY`, `MSME_JWT_SECRET`
- [ ] Enable TLS/HTTPS for all external endpoints
- [ ] Restrict callback endpoints to pawaPay IP ranges (if available)
- [ ] Remove `Bearer dummy-token` shortcut from `security.py`

### Observability
- [ ] Add structured logging (JSON format)
- [ ] Configure log aggregation (CloudWatch, DataDog, etc.)
- [ ] Set up Prometheus scraping for `/metrics` endpoint
- [ ] Create alerts for:
  - Reconciliation failures (`errors > 0`)
  - Stuck outbox rows (`status=pending AND created_at < NOW() - INTERVAL '1 hour'`)
  - Failed outbox deliveries (`status=failed`)
  - High callback error rates (400/500 responses)

### Background Jobs
- [ ] **Option A:** Add K8s CronJob to call `/jobs/outbox/flush` every 1-5 minutes
- [ ] **Option B:** Run separate worker container with background loop:
  ```python
  # worker.py
  import asyncio, httpx
  async def flush_loop():
      while True:
          async with httpx.AsyncClient() as client:
              await client.post("http://payment-revenue:8590/jobs/outbox/flush", 
                              headers={"Authorization": "Bearer internal-worker-token"})
          await asyncio.sleep(60)
  asyncio.run(flush_loop())
  ```
- [ ] Enable reconciliation background job: `PAWAPAY_RECONCILE_ENABLED=true`

### Data & Idempotency
- [ ] Verify idempotency keys work for deposits/payouts/refunds
- [ ] Test retry scenarios (network failures, timeouts)
- [ ] Set up DB backups (Postgres automated backups)
- [ ] Configure connection pooling for production scale

### Testing
- [ ] Run integration tests against sandbox:
  ```bash
  cd services/payment-revenue
  pytest tests/ -v
  ```
- [ ] Test callback retry with exponential backoff
- [ ] Test reconciliation loop (disable callbacks, trigger manual reconcile)
- [ ] Load test: simulate 100+ concurrent deposits

### Deployment
- [ ] Use CI/CD to run `alembic upgrade head` before deploying new code
- [ ] Zero-downtime deployment strategy (rolling updates, blue-green)
- [ ] Smoke test after deploy (health check + sample deposit)
- [ ] Rollback plan if deposit callbacks fail

---

## 📋 Quick Start Commands

**Local dev (docker-compose):**
```bash
# Start all services
docker-compose up -d

# Run migrations
docker-compose exec payment-revenue sh -c "pip install alembic && alembic upgrade head"

# Tail logs
docker-compose logs -f payment-revenue

# Trigger outbox flush
curl -X POST http://localhost:8590/jobs/outbox/flush -H "Authorization: Bearer dummy-token"
```

**Production deploy (example K8s):**
```bash
# Apply migration job
kubectl apply -f k8s/payment-revenue-migration-job.yaml
kubectl wait --for=condition=complete job/payment-revenue-migrate

# Deploy service
kubectl apply -f k8s/payment-revenue-deployment.yaml
kubectl rollout status deployment/payment-revenue

# Setup CronJob for outbox flusher
kubectl apply -f k8s/outbox-flush-cronjob.yaml
```

---

## 🔍 Monitoring Queries

**Check pending outbox rows:**
```sql
SELECT topic, destination, status, attempts, last_error, created_at 
FROM payment_revenue.outbox 
WHERE status = 'pending' 
ORDER BY created_at DESC 
LIMIT 50;
```

**Check failed deliveries:**
```sql
SELECT topic, destination, attempts, last_error, created_at 
FROM payment_revenue.outbox 
WHERE status = 'failed' 
ORDER BY created_at DESC 
LIMIT 50;
```

**Check recent deposits:**
```sql
SELECT deposit_id, status, amount_minor, currency, phone_number, provider, created_at, updated_at 
FROM payment_revenue.pawapay_deposits 
ORDER BY created_at DESC 
LIMIT 20;
```
