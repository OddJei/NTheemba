from fastapi import FastAPI

from .routers import intent

app = FastAPI(title="Bot Intent Service")

app.include_router(intent.router)
