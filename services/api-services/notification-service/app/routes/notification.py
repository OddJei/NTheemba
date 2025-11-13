from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel
from typing import List
from app.models.schemas import NotificationCreate, NotificationRead
from fastapi import Request, Header
from app.controllers.notification_controller import send_notification
from app.models.db import AsyncSessionLocal
from app.models.notifications import Notification
from sqlalchemy import select
from app.utils.audit import log_event
import asyncio

router = APIRouter(prefix="/notification", tags=["notification"])


@router.post("/send", response_model=NotificationRead, status_code=http_status.HTTP_201_CREATED)
async def api_send_notification(payload: NotificationCreate, request: Request, x_request_id: str | None = Header(None)):
    """Send a notification (creates DB record and dispatches send)."""
    metadata = {"request_id": x_request_id or "", "ip": request.client.host if request.client else ""}
    notification = await send_notification(payload, metadata=metadata)
    if not notification:
        raise HTTPException(status_code=500, detail="failed to create notification")
    return notification


@router.get("/{id}", response_model=NotificationRead)
async def api_get_notification(id: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Notification).filter_by(id=id))
        n = result.scalar_one_or_none()
        if not n:
            raise HTTPException(status_code=404, detail="notification not found")
        try:
            asyncio.create_task(
                log_event(
                    service="notification-service",
                    event_type="notification_viewed",
                    actor_id=(n.user_id or "system"),
                    entity_type="notification",
                    entity_id=n.id,
                    payload={"status": n.status},
                    metadata={"request_id": "", "ip": "127.0.0.1"},
                )
            )
        except Exception:
            pass
        return n


@router.get("/user/{user_id}", response_model=List[NotificationRead])
async def api_list_user_notifications(user_id: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Notification).filter_by(user_id=user_id).order_by(Notification.created_at.desc()))
        return result.scalars().all()
