Notification Service — Production Readiness Guide

Purpose
-------

This document lists concrete, actionable steps and configuration to make the Notification Service production-ready and able to reliably handle ~500 concurrent users. It covers configuration, runtime, observability, deployment, testing, and operational runbook items.

Summary judgment (short)
------------------------

The application is a good async-first foundation (FastAPI + async SQLAlchemy). Before production, you should implement DB pool tuning, HTTP client reuse, background delivery (worker/queue), observability, and load testing. The checklist below prioritizes these items and gives example configurations and commands.

Priority checklist (apply in order)
-----------------------------------

1. Database: configure connection pool, migrations, backups, and connection limits.
2. Outbound clients: reuse httpx.AsyncClient globally (don't create per-request).
3. Background delivery: offload external notifier calls to a worker/queue (Redis + RQ/Celery or a dedicated background process).
4. Process model: run multiple workers/processes and tune per-process DB pool sizes to keep total DB connections under Postgres limits.
5. Observability: add Prometheus metrics, request tracing (OpenTelemetry), structured logs, and health checks.
6. Reliability: add retries, exponential backoff and a circuit breaker for notifier calls; use a DLQ for permanent failures.
7. Load testing: create a Locust/k6 plan and validate 500 concurrent users in a staging environment.
8. Deployment & CI/CD: containerize, define resource limits, readiness/liveness probes, and automated migration steps.

Configuration & code snippets
-----------------------------

1) Database connection pool (app/models/db.py)

```python
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config.settings import settings

DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))

engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_timeout=DB_POOL_TIMEOUT,
    future=True,
)

AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()
```

Notes: tune DB_POOL_SIZE per process so total_connections = replicas *workers_per_replica* DB_POOL_SIZE <= postgres_max_connections - reserved.

2) Shared httpx client (app/utils/http_client.py)

```python
import httpx
from typing import Optional

_client: Optional[httpx.AsyncClient] = None

def get_http_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        limits = httpx.Limits(max_keepalive_connections=50, max_connections=200)
        _client = httpx.AsyncClient(timeout=5.0, limits=limits)
    return _client
```

Use `get_http_client()` in gateways instead of `async with httpx.AsyncClient()`.

3) Background worker (high level)

- Persist notification row in DB synchronously in API request.
- Enqueue message to Redis (RQueue, Redis Streams, or Celery).
- Worker consumes messages and calls notifier/gateway, updating notification status, with retries and DLQ.

4) Run command (example production start)

```powershell
# example using gunicorn + uvicorn workers
gunicorn -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8285 app.main:app --log-level info
```

Tune worker count to cores; scale horizontally with a load balancer.

Healthchecks & readiness
------------------------

- /health/live : returns 200 if server process is healthy.
- /health/ready: checks DB connection, Redis connectivity, and returns 200 when the app is ready to accept traffic.

Observability
-------------

- Expose /metrics via Prometheus client (track request latencies, DB pool usage, external call latencies, queue sizes).
- Add OpenTelemetry traces to capture request -> DB -> worker -> notifier flows.
- Ensure structured JSON logs (include request_id, user_id, notification_id, AUDIT_ENABLED, NOTIFIER_ENABLED).

Retries & circuit breaker
-------------------------

- Use exponential backoff for outbound notifier calls, with a max retry count (e.g., 3) and incrementally increase delay.
- Use a circuit-breaker pattern for the notifier to avoid cascading failures.

Load testing (Locust example)
-----------------------------

1. Install: `pip install locust`
2. Create `locustfile.py` with a POST to `/notification/send`.
3. Run headless: `locust -f locustfile.py --host http://<host>:8285 --users 500 --spawn-rate 50 --headless`
4. Monitor metrics and Postgres connections while running and tune pool/workers accordingly.

Deployment recommendations
--------------------------

- Containerize app (Docker), run multiple replicas behind a load balancer (NGINX or cloud LB).
- Use readiness/liveness probes.
- Apply rolling upgrades and health checks before draining traffic.
- Migrations: run `alembic upgrade head` as a separate CI/CD job before switching traffic.

Security
--------

- Keep secrets out of repo. Use a secrets manager (Vault, AWS Secrets Manager, Kubernetes Secrets).
- Serve only over TLS in production.
- Add rate limiting and authentication on endpoints that create notifications if intended.

Backup & DB maintenance
-----------------------

- Regular backups of Postgres (pg_dump or managed provider snapshots).
- Monitor long-running transactions and vacuum/analyze schedules.

CI/CD / Test automation
-----------------------

- Run unit tests + integration tests in CI with a disposable Postgres for DB migrations.
- Run migrations in a migration stage/step and report failures before deployment.

Operational runbook (short)
---------------------------

- To scale up: increase replica count in deployment and ensure DB has headroom.
- To debug high latency: check external notifier latency, DB slow queries, and worker queue backlog.
- To roll back: revert deployment, and re-run migration rollback if necessary (avoid destructive migrations without backward compatibility).

Next concrete work I can do for you (pick one)
----------------------------------------------

A) Implement DB pool env-driven config in `app/models/db.py` and run tests.  
B) Add `app/utils/http_client.py` and update gateway adapters to use shared client.  
C) Implement a simple Redis enqueue + worker skeleton and demo.  
D) Create a Locust load test and run a quick smoke of 100 concurrent users.

If you pick one, I will implement it and run tests here.

Appendix: quick tuning suggestion for 500 concurrent users
---------------------------------------------------------

- Start with: 3 replicas, each with 2 workers (uvicorn) and DB_POOL_SIZE=20 -> total DB connections = 3 *2* 20 = 120. Ensure Postgres max_connections >= 150.
- Use Redis-backed worker(s) to decouple external notifier calls so the API remains low-latency.
- Run a load test and watch 95th/99th percentile latency; adjust pool/workers accordingly.

Contact
-------

For help applying any of the code changes above, tell me which item (A-D) to implement and I will proceed and run the relevant tests.
