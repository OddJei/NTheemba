from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field, AliasChoices


class Attachment(BaseModel):
    name: str = Field(..., description="Attachment filename, e.g. 00_preamble.txt")
    content: str = Field(..., description="Text content to feed into Gemini")
    size: int = Field(..., description="Number of characters in content")


class IntentRequest(BaseModel):
    # Canonical identifiers
    event_id: str = Field(
        ...,
        description="Stable event identifier for correlation",
        validation_alias=AliasChoices("event_id", "request_id"),
    )
    session_id: str

    # Routing / context
    bot_id: Optional[str] = None
    bot_type: str = Field(default="default")
    trace_id: Optional[str] = None

    # User content
    raw_text: str = Field(
        ...,
        description="Normalized/plaintext user message",
        validation_alias=AliasChoices("raw_text", "normalized_text"),
    )

    # Optional enriched meta from bots/ingress
    enriched_meta: Dict[str, Any] = Field(default_factory=dict)

    # Optional extra context
    attachments: List[Attachment] = Field(default_factory=list)

class IntentInfo(BaseModel):
    id: str
    name: Optional[str] = None
    confidence: float = 0.0


class IntentResponse(BaseModel):
    event_id: str
    session_id: str

    intent: IntentInfo
    slots: Dict[str, Any] = Field(default_factory=dict)

    intent_required: bool = Field(default=False)
    next_action: Literal["reply", "outbound", "none"] = Field(default="reply")

    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    raw_input: Optional[str] = None

    # Backward-compatible fields
    request_id: Optional[str] = Field(default=None, exclude=True)
    confidence: Optional[float] = Field(default=None, exclude=True)
    entities: Optional[Dict[str, Any]] = Field(default=None, exclude=True)
    next_node: Optional[str] = None
    clarifying_question: Optional[str] = None
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    attachments: List[str] = Field(default_factory=list, description="Attachment names that were sent")

    def as_stream_dict(self) -> Dict[str, str]:
        # Keep a canonical JSON payload and a few indexed fields.
        return {
            "payload": self.model_dump_json(),
            "event_id": str(self.event_id or ""),
            "session_id": str(self.session_id or ""),
            "intent_id": str(self.intent.id if self.intent else ""),
            "next_action": str(self.next_action or ""),
        }
