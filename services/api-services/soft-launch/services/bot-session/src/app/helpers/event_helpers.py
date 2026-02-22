from __future__ import annotations

import uuid
import os
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

import os
from .outbox.outbox import create_outbox_row


async def emit_session_cycle_created_outbox(
    db: AsyncSession,
    *,
    session_id: str,
    cycle_id: str,
    cycle_state: str,
    affiliate_id: Optional[str] = None,
    user_phone: Optional[str] = None,
    business_id: Optional[str] = None,
    occurred_at: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> None:
    """Enqueue an Outbox event for `events/session-cycle-created` (Affiliate Engine).

    Uses the shared `create_outbox_row` helper which inserts into `outbox_events`.
    Caller will get a pending outbox row processed by the local dispatcher.
    """
    base = os.getenv("AFFILIATE_ENGINE_BASE_URL") or "http://affiliate-engine:8510"
    base = base.rstrip("/")
    target = f"{base}/events/session-cycle-created"

    payload = {
        "event_id": cycle_id,
        "event_type": "session_cycle_created",
        "occurred_at": occurred_at,
        "correlation_id": correlation_id or cycle_id,
        "producer": "bot-session",
        "affiliate_id": affiliate_id,
        "session_id": session_id,
        "cycle_id": cycle_id,
        "cycle_state": cycle_state,
        "user_phone": user_phone,
        "business_id": business_id,
        "meta": meta or {},
    }

    # Write into service schema outbox_events when available so the local
    # outbox-dispatcher or external pollers can pick up service-scoped rows.
    schema = os.getenv("PG_SCHEMA") or "bot_session"
    table = f"{schema}.outbox_events"
    await create_outbox_row(db, "session_cycle_created", payload, correlation_id=correlation_id, idempotency_key=idempotency_key, table=table)
    await db.commit()
