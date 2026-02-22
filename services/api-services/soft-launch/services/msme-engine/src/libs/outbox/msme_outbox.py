from __future__ import annotations

import uuid
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.models_outbox import OutboxEvent


async def create_msme_outbox_row(
    db: AsyncSession,
    topic: str,
    payload: Optional[Dict[str, Any]] = None,
    *,
    target: Optional[str] = None,
    destination: Optional[str] = None,
    headers: Optional[Dict[str, Any]] = None,
    producer: Optional[str] = None,
    correlation_id: Optional[str] = None,
    dedupe_key: Optional[str] = None,
    status: str = "pending",
    attempts: int = 0,
    priority: int = 0,
    commit: bool = True,
) -> None:
    """Insert a row into msme_engine.outbox_events.

    By default this helper will commit the transaction; set `commit=False`
    if the caller wants to make the insert atomic with other changes.
    """
    event = OutboxEvent(
        id=uuid.uuid4(),
        target=target,
        topic=topic,
        destination=destination,
        headers=headers,
        producer=producer,
        correlation_id=correlation_id,
        dedupe_key=dedupe_key,
        last_response=payload,
        status=status,
        attempts=attempts,
        priority=priority,
    )

    try:
        db.add(event)
        if commit:
            await db.commit()
        else:
            await db.flush()
    except SQLAlchemyError:
        # let caller observe/handle exceptions; roll back to clean session
        try:
            await db.rollback()
        except Exception:
            pass
        raise
