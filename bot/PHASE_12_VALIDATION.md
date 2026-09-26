# Ntheemba Phase 12 Validation

## Automated validation

## Packaging result

```text
358 automated tests passed
Python compilation passed
Observability self-check passed
Phase 11.20 contract-freeze acceptance passed
Phase 12 durability self-check passed
```


Run:

```bash
pytest -q
python -m compileall -q ntheemba scripts
python scripts/validate_observability.py
python scripts/validate_phase_11_20.py
python scripts/validate_phase_12.py
```

The Phase 12 suite covers:

- configuration and required DSNs;
- seven-day sessions and 90-day archives;
- revision conflicts and restart recovery;
- distributed lock ownership;
- deduplication and shared idempotency;
- TradeFlow write replay;
- unknown capability/method rejection;
- explicit customer consent;
- tenant-scoped saved addresses;
- exact business-channel routing;
- gateway ingestion authentication;
- gateway ack/retry/dead-letter behavior;
- stale Redis Stream claim recovery;
- multi-instance session and idempotency behavior;
- migration capability declarations, RLS, channel seeds, and retention scope;
- developer storage diagnostics;
- Phase 11.20 end-to-end simulator acceptance.

## Live Redis/PostgreSQL validation

This requires Docker or equivalent services:

```powershell
docker compose -f .\docker-compose.phase12.yml up -d
docker compose -f .\docker-compose.phase12.yml ps
python scripts\migrate_postgres.py `
  --dsn "postgresql://ntheemba:ntheemba_local_change_me@localhost:5432/ntheemba"
python scripts\validate_storage.py
```

Expected result:

```text
Storage self-check passed
```

Then start:

```powershell
python -m uvicorn ntheemba.main:app --reload
```

Check:

```text
http://127.0.0.1:8000/ready
http://127.0.0.1:8000/dev/storage
http://127.0.0.1:8000/dev/simulator/workspace
```

## Environment limitation during packaging

The packaging environment did not contain the `redis`, `psycopg`, `ruff`, or
`mypy` packages and did not run external Redis/PostgreSQL services. Therefore:

- the complete dependency-free automated suite and compile checks were run;
- live service checks are provided but not claimed as executed;
- Ruff and MyPy commands are provided but not claimed as passed here.

Run locally after `python -m pip install -e ".[dev]"`:

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy ntheemba tests
```
