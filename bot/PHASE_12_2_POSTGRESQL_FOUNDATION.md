# Phase 12.2 — PostgreSQL Foundation

Phase 12.2 adds an asynchronous Psycopg pool, ordered SQL migrations, tenant-aware repository transactions, readiness checks and PostgreSQL 16 Docker support.

Apply migrations with:

```powershell
python scripts\migrate_postgres.py --dsn $env:NTHEEMBA_POSTGRES_DSN
```

Use a dedicated application role in production. Do not connect the API as a PostgreSQL superuser because superusers bypass row-level security.
