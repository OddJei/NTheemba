from typing import Optional, Dict
from fastapi import Request
from app.models.schemas import NotificationCreate
from app.services.notification_service import NotificationService


async def send_notification(payload: NotificationCreate, metadata: Optional[Dict] = None):
    svc = NotificationService()
    return await svc.create_and_send(payload, metadata=metadata)
