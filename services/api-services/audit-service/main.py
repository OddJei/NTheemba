from fastapi import FastAPI
from routes.audit_routes import router as audit_router
from config import settings
from core.database import init_db

app = FastAPI(title="audit-service")

app.include_router(audit_router, prefix="/audit", tags=["audit"])


@app.on_event("startup")
def on_startup():
    # Ensure DB tables exist on startup (convenience for dev). For production use Alembic migrations.
    init_db()


@app.get("/health")
def health():
    return {"ok": True, "service": "audit"}


if __name__ == '__main__':
    import uvicorn
    port = getattr(settings, 'PORT', 8290)
    uvicorn.run("main:app", host="0.0.0.0", port=port)
