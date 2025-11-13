from typing import Optional, Dict
from fastapi import Request
from app.models.schemas import PreferenceUpdate
from app.services.preference_service import PreferenceService


async def update_preference(payload: PreferenceUpdate, metadata: Optional[Dict] = None):
    svc = PreferenceService()
    return await svc.update_or_create(payload, metadata=metadata)


async def get_preference(user_id: str, metadata: Optional[Dict] = None):
    svc = PreferenceService()
    return await svc.get_by_user(user_id, metadata=metadata)
