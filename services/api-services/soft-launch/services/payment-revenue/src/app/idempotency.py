from __future__ import annotations

from typing import Any, Awaitable, Callable, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models import IdempotencyRecord


def scope_for(method: str, path: str) -> str:
    return f"{method.upper()} {path}"


async def idempotent_execute(
    *,
    db: AsyncSession,
    scope: str,
    key: str | None,
    run: Callable[[], Awaitable[Tuple[int, Any]]],
) -> Tuple[int, Any]:
    if not key:
        return await run()

    existing = (await db.execute(select(IdempotencyRecord).where(IdempotencyRecord.scope == scope, IdempotencyRecord.key == key))).scalar_one_or_none()
    if existing:
        return int(existing.status_code), existing.response_body

    status, body = await run()
    if hasattr(body, "model_dump"):
        body = body.model_dump(mode="json")
    db.add(IdempotencyRecord(scope=scope, key=key, status_code=int(status), response_body=body))
    await db.commit()
    return int(status), body
