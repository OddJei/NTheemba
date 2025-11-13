from __future__ import annotations

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
    locale: str = "en"


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
        return {"payload": self.json(by_alias=True)}
