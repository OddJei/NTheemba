from typing import Any, Optional
from pydantic import BaseModel
from datetime import datetime


class NotificationCreate(BaseModel):
    user_id: Optional[str] = None
    business_id: Optional[str] = None
    channel: str
    template: Optional[str] = None
    payload: Optional[Any] = None


class NotificationRead(BaseModel):
    id: str
    user_id: Optional[str]
    business_id: Optional[str]
    channel: str
    template: Optional[str]
    payload: Optional[Any]
    status: str
    error_message: Optional[str]
    created_at: datetime
    sent_at: Optional[datetime]

    class Config:
        orm_mode = True


class TemplateCreate(BaseModel):
    name: str
    channel: str
    content: str


class TemplateRead(BaseModel):
    id: str
    name: str
    channel: str
    content: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True


class PreferenceUpdate(BaseModel):
    user_id: str
    preferred_channel: Optional[str] = None
    opt_in: Optional[bool] = None


class PreferenceRead(BaseModel):
    id: str
    user_id: str
    preferred_channel: Optional[str]
    opt_in: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True
