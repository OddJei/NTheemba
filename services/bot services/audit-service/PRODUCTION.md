## Audit Service — Production Readiness

This document captures production readiness guidance, checklists and concrete commands to deploy and operate the Audit Service safely and at scale.

Keep this file in the root of the `audit-service` directory and update it as you harden, deploy, and operate the service.

---

## Quick status

- Service persists audit events to Postgres using `audit_service.audit_logs` (Alembic migrations included).
- Health endpoint: `GET /health`

## High-priority checklist (must complete before production)

1. Disable automatic schema creation in production
   - Do not call `init_db()` on startup in production. Use Alembic migrations instead.
   - Recommended: guard `init_db()` with an env var (e.g. `DEV_INIT_DB=true`).

2. Ensure Alembic migrations are applied on deploy
   - Run `alembic upgrade head` in your deployment pipeline or during a DB migration job.
   - If you previously used `init_db()` to create tables in dev, use `alembic stamp head` to mark migrations applied.

3. Align Alembic version table with service schema
   - Option A (one-off): Move `alembic_version` into the service schema:
     `ALTER TABLE public.alembic_version SET SCHEMA audit_service;`
   - Option B (code): set `version_table_schema=SERVICE_SCHEMA` in `alembic/env.py` (both offline and online configs).

4. Use request-scoped DB sessions via FastAPI dependencies
   - Implement `get_db()` dependency that yields a `SessionLocal()` and closes it in `finally`.
   - Inject DB sessions into controllers using `Depends(get_db)`.

5. Replace raw JSON parsing with Pydantic schemas
   - Define input models for audit events and response models for queries.
   - This improves validation and auto-generated OpenAPI docs.

6. Harden the image and runtime
   - Use Gunicorn with Uvicorn workers in production.
     Example CMD: `gunicorn -k uvicorn.workers.UvicornWorker -w ${GUNICORN_WORKERS:-4} --bind 0.0.0.0:8290 main:app`
   - Run as a non-root user; consider a multi-stage build to minimize image size.
   - Add a container HEALTHCHECK that probes `/health`.

7. Tune DB pool and worker configuration
   - Expose env vars and set reasonable defaults in `core/database.py`:
     - `DB_POOL_SIZE` (default 5)
     - `DB_MAX_OVERFLOW` (default 10)
     - `DB_POOL_TIMEOUT` (default 30)
   - Calculate total DB connection budget: `(pool_size + max_overflow) * workers * pods` and ensure Postgres `max_connections` is large enough or use PgBouncer.

8. Add connection pooling layer (PgBouncer)
   - Deploy PgBouncer in front of Postgres to multiplex many client connections onto fewer Postgres sessions.

9. Introduce batching for high throughput
   - Accept events quickly and write them to DB in batches (bulk inserts or COPY) from a background worker or consumer.
   - Tune batch size and flush interval by load tests.

10. Add observability, metrics & tracing
    - Instrument request latency, RPS, DB connection usage, queue length (if batching), and error rates
    - Export Prometheus metrics and create dashboards and alerts (high latency, connection saturation, error rate).

11. CI/CD: migrations and integration tests
    - Pipeline should: lint → unit tests → build image → push image → deploy to staging → `alembic upgrade head` → run integration & contract tests → promote.

12. Security & governance
    - Store secrets in a secret manager (Vault, cloud secret store).
    - Use scoped DB accounts with least-privilege for the app.
    - Add RBAC for query/export endpoints and rate limiting for ingest endpoints.

13. Tests and QA
    - Add unit tests, integration tests against a real Postgres (TestContainers or CI DB), and consumer contract tests (Pact).

---

## Example environment variables

- `AUDIT_DATABASE_URL` or `PG_USER`/`PG_PASSWORD`/`PG_DB`/`PG_HOST`
- `SERVICE_SCHEMA` (defaults to `audit_service`)
- `DEV_INIT_DB` (when true the service will call `init_db()` at startup; do not enable in production)
- `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`
- `GUNICORN_WORKERS`

## Useful commands (dev / ops)

Create DB (helper script; requires `psycopg2`):

```powershell
# from services/api-services/audit-service
python .\tools\create_db.py
```

Apply Alembic migrations:

```powershell
# with venv activated from the audit-service folder
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Stamp current DB as up-to-date (use if tables were created by `init_db()` previously):

```powershell
.\.venv\Scripts\python.exe -m alembic stamp head
```

Start the app in dev (auto-init enabled for convenience):

```powershell
uvicorn main:app --reload
```

Recommended production container runtime (example):

```dockerfile
# use Gunicorn + Uvicorn workers
CMD ["gunicorn","-k","uvicorn.workers.UvicornWorker","-w","4","--bind","0.0.0.0:8290","main:app"]
```

Basic DB pool configuration snippet (example for `core/database.py`):

```python
engine = create_engine(
    DATABASE_URL,
    pool_size=int(os.getenv('DB_POOL_SIZE','5')),
    max_overflow=int(os.getenv('DB_MAX_OVERFLOW','10')),
    pool_timeout=int(os.getenv('DB_POOL_TIMEOUT','30')),
    pool_pre_ping=True,
)
```

## Load testing

- Create a k6 or locust script that POSTs sample audit events. Simulate 500 concurrent users and observe:
  - request latency (p95/p99), error rate
  - DB connection counts
  - CPU/memory of pods

Iterate tuning workers, pool sizes and batch sizes until service meets SLA.

## Operational runbook highlights

- If DB connections reach a high percentage of `max_connections`: scale down per-process pool_size or enable PgBouncer.
- If latency climbs under load: increase workers/pods, enable batching, ensure Postgres has enough IOPS/memory.
- For long-running export jobs use a separate worker process or job queue with object storage (S3/MinIO) for large exports.

## Migration to higher-scale architecture (when needed)

- Replace synchronous DB writes with a producer → message queue (Kafka/Rabbit) → consumer(s) that write in batches.
- Or migrate to async DB driver (asyncpg + SQLAlchemy async) for better concurrency per process (requires refactor).

## Contacts & references

- Repo path: `services/api-services/audit-service`
- Migrations: `alembic/versions`
- DB core: `core/database.py`

---

If you'd like, I can also:

- add a hardened `Dockerfile` and `gunicorn` CMD,
- patch `core/database.py` to expose pool env vars,
- create a simple k6 load test and a run guide,
- modify `alembic/env.py` to set `version_table_schema=SERVICE_SCHEMA`.

Pick which of the above you'd like me to add and I'll create the changes.
