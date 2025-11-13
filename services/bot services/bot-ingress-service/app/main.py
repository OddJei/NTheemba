import asyncio
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

from fastapi import FastAPI

# Load environment variables from app/.env so this service can run independently.
# This will not raise if the file is missing when python-dotenv is installed; it simply won't override existing env vars.
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

from .core.config import get_settings
from .core.redis import get_redis, close_redis
from .workers.queue_listener import start_listener

LOG = logging.getLogger("bot-ingress.main")

app = FastAPI()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.on_event("startup")
async def startup():
    settings = get_settings()
    app.state.settings = settings
    app.state.redis = get_redis(settings)
    # start background listener
    app.state.listener_task = asyncio.create_task(start_listener(app.state.redis, settings))
    LOG.info("bot-ingress started")


@app.on_event("shutdown")
async def shutdown():
    task = getattr(app.state, "listener_task", None)
    if task:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    await close_redis()
    LOG.info("bot-ingress stopped")


if __name__ == "__main__":
    import uvicorn

    # default to port 5200 so the service runs independently on the requested port
    # allow overriding with the PORT environment variable
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "5200")), log_level="info")
