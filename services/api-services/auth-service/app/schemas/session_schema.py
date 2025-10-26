from pydantic import BaseModel
from datetime import datetime
from typing import Any, Dict

class SessionValidateRequest(BaseModel):
    token: str

class SessionValidateResponse(BaseModel):
    valid: bool
    claims: Dict[str, Any] | None = None
