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

```powershell
# with venv activated
python -c "from core.database import init_db; init_db(); print('db initialized')"
```

To apply Alembic migrations (recommended for production):

```powershell
# ensure PG_* env vars are set in your shell (or export them), then:
.\.venv\Scripts\python.exe -m alembic upgrade head
```

4. Start the app (runs on port 8290 by default):

```powershell
uvicorn main:app --reload
```

Files of interest:
- `main.py` - FastAPI entrypoint
- `core/database.py` - SQLAlchemy engine and Base
- `models/audit.py` - AuditLog model
- `routes/audit_routes.py` - API routes
- `controllers/audit_controller.py` - request handling
- `services/audit_service.py` - ingestion logic
