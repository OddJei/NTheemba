from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional, Tuple, TypeVar

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models import IdempotencyRecord

T = TypeVar("T")


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return jsonable_encoder(value)


async def idempotent_execute(
    *,
    db: AsyncSession,
    scope: str,
    key: Optional[str],
    run: Callable[[], Awaitable[Tuple[int, Any]]],
) -> Tuple[int, Any]:
    if not key:
        return await run()

    existing = (
        await db.execute(select(IdempotencyRecord).where(IdempotencyRecord.scope == scope, IdempotencyRecord.key == key))
    ).scalar_one_or_none()
    if existing:
        return int(existing.status_code), existing.response_json

    status_code, body = await run()
    json_body = _to_jsonable(body)

    record = IdempotencyRecord(scope=scope, key=key, status_code=int(status_code), response_json=json_body)
    db.add(record)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = (
            await db.execute(
                select(IdempotencyRecord).where(IdempotencyRecord.scope == scope, IdempotencyRecord.key == key)
            )
        ).scalar_one_or_none()
        if existing:
            return int(existing.status_code), existing.response_json
        raise

    return int(status_code), json_body


def scope_for(method: str, path: str) -> str:
    return f"{method.upper()} {path}"
