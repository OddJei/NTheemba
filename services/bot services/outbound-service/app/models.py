from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class OutboundRequest(BaseModel):
    event_id: str
    session_id: str
    # legacy `provider` field kept for backward compatibility; prefer `meta.platform`
    provider: Optional[str] = Field(None, description="Legacy provider/platform: wa|sms|http|...")
    meta: Dict[str, Any] = Field(default_factory=dict)
    provider_payload: Dict[str, Any] = Field(default_factory=dict)
    delivery_instructions: Dict[str, Any] = Field(default_factory=dict)
    callback_url: Optional[str] = None
    trace_id: Optional[str] = None

    attempts: int = 0


class ProviderError(BaseModel):
    code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class DeliveryReceipt(BaseModel):
    event_id: str
    session_id: str
    provider: str
    provider_message_id: str
    status: str  # queued|sent|delivered|failed
    timestamp: str
    provider_error: Optional[Dict[str, Any]] = None
    trace_id: Optional[str] = None

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()


class DlqEntry(BaseModel):
    event_id: str
    session_id: str
    provider: str
    attempts: int
    error: Dict[str, Any]
    original_request: Dict[str, Any]
    timestamp: str

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
