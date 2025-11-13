from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Attachment(BaseModel):
    name: str = Field(..., description="Attachment filename, e.g. 00_preamble.txt")
    content: str = Field(..., description="Text content to feed into Gemini")
    size: int = Field(..., description="Number of characters in content")


class IntentRequest(BaseModel):
    request_id: str
    session_id: str
    session_mode: str
    bot_type: str
    current_node: Optional[str] = None
    allowed_actions: List[str] = Field(default_factory=list)
    reachable_nodes: List[str] = Field(default_factory=list)
    normalized_text: str
    attachments: List[Attachment] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class IntentResponse(BaseModel):
    request_id: str
    session_id: str
    intent: str
    confidence: float
    entities: Dict[str, Any] = Field(default_factory=dict)
    next_node: Optional[str] = None
    clarifying_question: Optional[str] = None
    model: str = Field(default="gemini-1.5-pro")
    tokens_used: Optional[int] = None
    attachments: List[str] = Field(default_factory=list, description="Attachment names that were sent")
