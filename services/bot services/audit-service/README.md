# Audit Service

This service stores immutable audit events from other services and exposes query and export APIs.

Quick start (dev):

1. create a virtualenv and install deps:

```powershell
cd "c:\Users\SMART PC\Documents\NTheemba\services\api-services\audit-service"
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Configure Postgres connection (required)

Create or edit `config/.env` and set these values (example):

```
PG_USER=postgres
PG_PASSWORD=your_password_here
PG_DB=Ntheemba
PG_HOST=localhost
PORT=8290
```

Make sure the database `Ntheemba` exists and Postgres is reachable.

3. Initialize the DB (optional: Alembic recommended)

You can let the app create tables on startup (dev convenience) or run Alembic migrations.

To create tables automatically (dev):

# Audit Service — Run Instructions

This document explains how to run the `audit-service` in development on port `8290`.

**Prerequisites:**
- **Python:** 3.10+ installed
- **Postgres:** reachable database for `PG_*` env vars

**1. Change to service folder:**

```powershell
cd "C:\Users\SMART PC\Documents\NTheemba\services\api-services\audit-service"
```

**2. Create and activate virtual environment, install deps:**

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**3. Configure environment variables (Postgres + optional PORT):**

Create or edit `config/.env` (or set env vars in your shell). Example values:

```
PG_USER=postgres
PG_PASSWORD=your_password_here
PG_DB=Ntheemba
PG_HOST=localhost
PORT=8290
```

**4. Initialize DB (dev convenience):**

You can let the app create tables on startup (development) or run Alembic migrations for production.

```powershell
# quick create tables (with venv active)
python -c "from core.database import init_db; init_db(); print('db initialized')"

# or run Alembic (recommended for production)
.\.venv\Scripts\python.exe -m alembic upgrade head
```

**5. Start the service (runs on port 8290):**

Option A — run Uvicorn explicitly with the port:

```powershell
uvicorn main:app --reload --port 8290
```

Option B — use the included PowerShell wrapper which activates the venv and starts Uvicorn:

```powershell
./run.ps1
```

**Notes:**
- The `main.py` module's `if __name__ == '__main__'` block also uses `PORT=8290` by default (via `settings`), but the Uvicorn CLI only uses the port you pass; using `--port 8290` or the wrapper ensures the server listens on the intended port.
- If you want the `payment-service` or other folders ignored by Git, add paths to `.gitignore`.

**Files of interest:** `main.py`, `core/database.py`, `routes/audit_routes.py`, `models/audit.py`
