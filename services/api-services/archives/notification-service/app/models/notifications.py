import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, Text
from sqlalchemy.sql import func
from app.models.db import Base


class StatusEnum(str):
    pending = "pending"
    sent = "sent"
    failed = "failed"


class ChannelEnum(str):
    sms = "sms"
    email = "email"
    in_app = "in_app"


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = {"schema": "notification_service"}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=True)
    business_id = Column(String, nullable=True)
    channel = Column(String, nullable=False)
    template = Column(Text, nullable=True)
    payload = Column(JSON, nullable=True)
    status = Column(String, nullable=False, default=StatusEnum.pending)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    sent_at = Column(DateTime(timezone=True), nullable=True)
