from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .core.config import get_settings
from .core.redis import RedisClient
from .routers import intent
from .worker import worker_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
	settings = get_settings()
	worker_task: asyncio.Task | None = None

	if settings.worker_enabled:
		worker_task = asyncio.create_task(worker_loop())
		app.state.intent_worker_task = worker_task

	try:
		yield
	finally:
		if worker_task is not None:
			worker_task.cancel()
			try:
				await worker_task
			except Exception:
				pass

		await RedisClient.close()


app = FastAPI(title="Bot Intent Service", lifespan=lifespan)


@app.get("/healthz")
async def healthz():
	return {"ok": True, "service": get_settings().service_name}


app.include_router(intent.router)
