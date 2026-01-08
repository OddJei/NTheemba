# Bot-Session Unified Service (scaffold)

This folder contains a minimal scaffold for the unified Bot-Session + Event service.

Quick start (development):

1. Create a virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Run locally (sqlite default):

```powershell
setx DATABASE_URL "sqlite:///./dev.db"
uvicorn src.app.main:app --reload --port 8000
```

4. Run tests:

```powershell
pip install -r requirements.txt
pytest -q
```

3. Apply Postgres SQL migration (if using Postgres):

```psql
\i migrations/0001_create_tables.sql
```

Next steps: implement controllers and business logic per design docs.
