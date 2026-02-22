from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, conint
# Avoid call expressions inside annotations (pyright/pylance):
# create a top-level alias for a non-negative int type.
PositiveInt = conint(ge=0)
from datetime import datetime


class BotCreate(BaseModel):
    phone_number: str = Field(..., min_length=4, description="Bot phone number", json_schema_extra={"example": "+260971234567"})
    type: Optional[str] = Field("custom", description="Bot type", json_schema_extra={"example": "custom"})
    business_id: Optional[str] = Field(None, description="Business id", json_schema_extra={"example": "business_123"})


class BotCreateResponse(BaseModel):
    bot_id: str
    phone_number: str


class CreateSessionReq(BaseModel):
    bot_id: Optional[str] = Field(None, description="Existing bot id")
    bot_phone: Optional[str] = Field(None, description="Bot phone to resolve")
    user_phone: str = Field(..., min_length=4, description="End-user phone number", json_schema_extra={"example": "+260971234567"})
    platform: str = Field("default", description="Client platform", json_schema_extra={"example": "whatsapp"})
    business_id: Optional[str] = Field(None, description="Business id", json_schema_extra={"example": "business_123"})
    affiliate_id: Optional[str] = Field(None, description="Affiliate id", json_schema_extra={"example": "aff_123"})
    affiliate_metadata: Optional[Dict[str, Any]] = None


class CreateSessionResponse(BaseModel):
    session_id: str
    status: str
    reactivated: bool
    last_event_id: Optional[str]
    object_context: Optional[Dict[str, Any]]


class CreateEventReq(BaseModel):
    session_id: str = Field(..., description="Session id", json_schema_extra={"example": "sess_123"})
    event_type: str = Field(..., min_length=1, description="Event type", json_schema_extra={"example": "enter_cart"})
    bot_id: Optional[str] = Field(None, description="Bot id")
    user_phone: Optional[str] = Field(None, description="User phone")
    last_event_id: Optional[str] = Field(None, description="Previous event id")
    payload_events: Optional[Dict[str, Any]] = None


class CreateEventResponse(BaseModel):
    event_id: str
    session_id: str
    message_count: PositiveInt


class StateTransitionRequest(BaseModel):
    new_state: str
    context: Optional[Dict[str, Any]] = None
    affiliate_id: Optional[str] = None


class StateCycleUpgradeRequest(BaseModel):
    new_state: str
    context: Optional[Dict[str, Any]] = None
    affiliate_id: Optional[str] = None


class EventUpdateRequest(BaseModel):
    updated_fields: Optional[Dict[str, Any]] = None
    append_payload_event: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class EventResponse(BaseModel):
    id: str
    session_id: str
    event_type: str
    payload_events: Optional[Dict[str, Any]] = None
    previous_turns: Optional[List[Dict[str, Any]]] = None
    message_count: Optional[int] = None
    status: Optional[str] = None


class EventListItem(BaseModel):
    id: str
    event_type: str
    created_at: Optional[datetime] = None
    message_count: Optional[int] = None


class SessionCycleResponse(BaseModel):
    id: str
    cycle_state: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    initiated_by_affiliate: Optional[bool] = None
    affiliate_id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class SessionResponse(BaseModel):
    id: str
    user_phone: Optional[str] = None
    bot_id: Optional[str] = None
    platform: Optional[str] = None
    status: Optional[str] = None
    last_event_id: Optional[str] = None
    state: Optional[str] = None
    state_entered_at: Optional[datetime] = None


class SessionListItem(BaseModel):
    id: str
    bot_id: Optional[str] = None
    status: Optional[str] = None
