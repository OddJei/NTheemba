from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class InboundMeta(BaseModel):
    platform: str


class InboundMessage(BaseModel):
    request_id: str
    message: Optional[str] = None
    attachments: Optional[List[Any]] = Field(default_factory=list)
    to: str
    from_: str = Field(alias="from")
    timestamp: datetime
    meta: InboundMeta

    class Config:
        allow_population_by_field_name = True


class UserContext(BaseModel):
    id: Optional[str] = None
    phone: str
    roles: List[str]
    authenticated: bool
    business_id: Optional[str] = None
    locale: Optional[str] = "en"


class SessionContext(BaseModel):
    session_id: str
    session_mode: str
    bot_type: str
    current_node: Optional[str] = None
    started_at: datetime
    last_active_at: datetime
    reset_requested: bool = False


class SessionEventIngress(BaseModel):
    normalized_text: str
    attachments: List[Any]
    capabilities: List[str]
    allowed_actions: List[str]
    mode: str
    mode_id: str
    received_at: datetime
    user_session: Dict[str, Any]
    previous_events_count: int = 0


class SessionEvent(BaseModel):
    event_id: Optional[str]
    started_at: datetime
    ingress: SessionEventIngress


class BotMetadata(BaseModel):
    bot_details: Dict[str, Any]
    business_details: Dict[str, Any]
    owner_details: Dict[str, Any]


class EnrichedPayload(BaseModel):
    request_id: str
    event_id: Optional[str]
    message: Optional[str]
    to: str
    from_: str = Field(alias="from")
    timestamp: datetime
    meta: Dict[str, Any]

    class Config:
        allow_population_by_field_name = True

    def as_stream_dict(self) -> Dict[str, str]:
        meta = self.meta or {}

        session_val = meta.get("session") or {}
        if hasattr(session_val, "dict"):
            session = session_val.dict()
        else:
            session = session_val

        user_val = meta.get("user") or {}
        if hasattr(user_val, "dict"):
            user = user_val.dict()
        else:
            user = user_val

        bot_val = meta.get("bot") or {}
        bot_details = bot_val.get("bot_details") or {}
        if hasattr(bot_details, "dict"):
            bot_details = bot_details.dict()

        routing_hints = meta.get("routing_hints") or {}

        return {
            # Canonical JSON for replay/debugging.
            "payload": self.json(by_alias=True),
            # Indexed fields to match the architecture contract and enable quick routing/inspection.
            "event_id": str(self.event_id or ""),
            "request_id": str(self.request_id or ""),
            "session_id": str(session.get("session_id") or ""),
            "bot_type": str(session.get("bot_type") or ""),
            "bot_id": str(bot_details.get("id") or ""),
            "user_id": str(user.get("id") or ""),
            "routing_hints": json.dumps(routing_hints, ensure_ascii=False, default=str),
        }
