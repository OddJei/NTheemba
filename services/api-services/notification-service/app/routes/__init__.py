from fastapi import APIRouter

router = APIRouter(prefix="/notification", tags=["notification"])

from app.routes import notification  # noqa: F401
