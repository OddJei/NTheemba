from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ReplyRequest(BaseModel):
    # Required
    event_id: str
    session_id: str

    # Optional routing/context
    channel: Optional[str] = None
    locale: Optional[str] = "en"

    # Rendering inputs
    text: Optional[str] = None
    template_id: Optional[str] = None
    render_type: Optional[str] = None  # template|nlg
    template_vars: Dict[str, Any] = Field(default_factory=dict)

    # Metadata
    next_node: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    trace_id: Optional[str] = None
    span_id: Optional[str] = None


class OutboundRequest(BaseModel):
    event_id: str
    session_id: str
    provider: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    provider_payload: Dict[str, Any] = Field(default_factory=dict)
    delivery_instructions: Dict[str, Any] = Field(default_factory=dict)
    callback_url: Optional[str] = None
    trace_id: Optional[str] = None

    attempts: int = 0


class DlqEntry(BaseModel):
    event_id: str
    session_id: str
    error: Dict[str, Any]
    original_request: Dict[str, Any]
    timestamp: str

    @staticmethod
    def now_iso() -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()
