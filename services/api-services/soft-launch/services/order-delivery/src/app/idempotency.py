from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Tuple

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models import IdempotencyRecord


def scope_for(method: str, route_template: str) -> str:
    return f"{method.upper()} {route_template}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def idempotent_execute(
    *,
    db: AsyncSession,
    scope: str,
    key: str | None,
    run: Callable[[], Awaitable[Tuple[int, Any]]],
) -> Tuple[int, Any]:
    if not key:
        return await run()

    existing = (
        await db.execute(select(IdempotencyRecord).where(IdempotencyRecord.scope == scope, IdempotencyRecord.key == key))
    ).scalar_one_or_none()
    if existing:
        return int(existing.status_code), existing.response_body

    status, body = await run()

    record = IdempotencyRecord(
        id=str(uuid.uuid4()),
        scope=scope,
        key=key,
        status_code=int(status),
        response_body=body if isinstance(body, dict) else json.loads(json.dumps(body, default=str)),
        created_at=_utcnow(),
    )
    db.add(record)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = (
            await db.execute(select(IdempotencyRecord).where(IdempotencyRecord.scope == scope, IdempotencyRecord.key == key))
        ).scalar_one()
        return int(existing.status_code), existing.response_body

    return int(status), body
