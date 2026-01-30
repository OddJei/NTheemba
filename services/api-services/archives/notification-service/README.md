# Notification Service — Run Instructions

This short guide explains how to run the `notification-service` in development and ensures the server listens on port `8285`.

Prerequisites
- Python 3.10+ installed
- Any required external services configured (e.g. Redis, Postgres) and corresponding `PG_*`/`REDIS_*` env vars set if applicable

1) Change to the service folder

```powershell
cd "C:\Users\SMART PC\Documents\NTheemba\services\api-services\notification-service"
```

2) Create and activate a virtual environment, then install deps

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3) Configure environment variables

Create `config/.env` or export environment variables in your shell. Example:

```
PORT=8285
# Add DB or queue variables the service needs, e.g.:
# REDIS_URL=redis://localhost:6379
# PG_HOST=localhost
# PG_USER=postgres
# PG_PASSWORD=secret
```

4) Start the service (important: module path)

The code for this service is inside the `app` package. If you run `uvicorn main:app` you may see the error:

```
ERROR: Error loading ASGI app. Could not import module "main".
```

To avoid that use the package path `app.main:app` and pass `--port 8285`:

```powershell
uvicorn app.main:app --reload --port 8285
```

Or use the included PowerShell wrapper which activates the venv and runs Uvicorn for you:

```powershell
./run.ps1
```

Troubleshooting
- If Uvicorn reports `Could not import module "main"`, run with `app.main:app` as shown above.
- If dependencies are missing, ensure you installed `requirements.txt` in the active `.venv`.
- If the service needs other services (Redis, Postgres), ensure those are running and the env vars point to them.

Files of interest
- `app/main.py` — FastAPI entrypoint
- `requirements.txt` — Python deps
- `config/` — environment files (if present)

If you'd like, I can also add a `start.bat` for one-click Windows start or update `config/.env.example` with recommended env vars.
# Notification Service (scaffold)

Minimal scaffold for the Notification Service.

Run locally (recommended in a venv):

1. Install deps:

   pip install -r requirements.txt

2. Set env (use `.env.example` as template) and run:

   uvicorn app.main:app --reload --port 8000

3. Open http://127.0.0.1:8000/docs to see API docs.

This scaffold uses SQLite by default for quick local testing and provides stubbed gateway adapters.
