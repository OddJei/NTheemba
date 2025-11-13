from fastapi import FastAPI
from app.config.settings import settings
from app.models.db import engine, Base, AsyncSessionLocal
from app.routes import notification as notification_routes
from app.routes import template as template_routes
from app.routes import preferences as preferences_routes
from sqlalchemy import text
import os

try:
    import uvicorn
except Exception:
    uvicorn = None


def create_app() -> FastAPI:
    app = FastAPI(title="Notification Service")

    # include routers
    app.include_router(notification_routes.router)
    app.include_router(template_routes.router)
    app.include_router(preferences_routes.router)

    @app.on_event("startup")
    async def on_startup():
        # ensure schema exists for Postgres and create tables via async engine
        try:
            async with engine.begin() as conn:
                await conn.execute(text("CREATE SCHEMA IF NOT EXISTS notification_service"))
                # create tables
                await conn.run_sync(Base.metadata.create_all)
        except Exception:
            # ignore for sqlite/local dev if raw SQL not supported
            pass

    return app


app = create_app()


if __name__ == "__main__":
    # Allow overriding host/port via env, but default to settings.SERVICE_PORT (usually 8285)
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", str(settings.SERVICE_PORT)))
    use_reload = os.getenv("UVICORN_RELOAD", "1") in ("1", "true", "True")
    if uvicorn is None:
        raise RuntimeError("uvicorn is not installed; please run the app with 'uvicorn app.main:app' or install uvicorn")
    uvicorn.run("app.main:app", host=host, port=port, reload=use_reload)
