from __future__ import annotations

from typing import Optional, Dict, Any
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.helpers.outbox.outbox import create_outbox_row

logger = logging.getLogger(__name__)


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
    commit: bool = True,
) -> str:
    """Compatibility wrapper that writes into `msme_engine.outbox_events`.

    Delegates to the unified `create_outbox_row` implementation.
    """
    logger.debug("msme_outbox.create_msme_outbox_row - delegating to unified emitter", extra={"topic": topic})
    out_id = await create_outbox_row(
        db,
        topic,
        payload or {},
        destination=destination,
        headers=headers,
        producer=producer,
        correlation_id=correlation_id,
        idempotency_key=dedupe_key,
        commit=commit,
    )
    return str(out_id)
