# Notification Service (scaffold)

Minimal scaffold for the Notification Service.

Run locally (recommended in a venv):

1. Install deps:

   pip install -r requirements.txt

2. Set env (use `.env.example` as template) and run:

   uvicorn app.main:app --reload --port 8000

3. Open http://127.0.0.1:8000/docs to see API docs.

This scaffold uses SQLite by default for quick local testing and provides stubbed gateway adapters.
