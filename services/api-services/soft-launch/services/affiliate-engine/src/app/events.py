from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class OrderCreatedEvent(BaseModel):
    event_id: str
    event_type: str = "order_created"
    occurred_at: datetime
    correlation_id: str
    producer: str

    order_id: str
    business_id: str
    status: str
    total_amount: float
    currency: str

    session_id: Optional[str] = None
    user_phone: Optional[str] = None
    user_id: Optional[str] = None

    affiliate_code: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
