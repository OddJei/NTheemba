Minimal BFF prototype (FastAPI)

Quick start

1. Create a Python virtualenv and install dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Run Redis (local or docker)

3. Start the BFF:

```powershell
uvicorn src.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Endpoints
- `POST /login` - simple login that sets an HTTP-only session cookie
- `GET /dashboard` - example aggregated endpoint that calls the backend service
