"""In-memory idempotency adapter used for local development and tests."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from ntheemba.ports.idempotency import (
    IdempotencyRecord,
    IdempotencyStatus,
    IdempotencyStore,
)


class MemoryIdempotencyStore(IdempotencyStore):
    def __init__(self) -> None:
        self._records: dict[str, tuple[IdempotencyRecord, datetime]] = {}
        self._guard = asyncio.Lock()

    async def claim(self, key: str, *, owner_token: str, ttl: timedelta) -> bool:
        self._validate(key, owner_token, ttl)
        async with self._guard:
            self._purge_expired()
            if key in self._records:
                return False
            record = IdempotencyRecord(key, IdempotencyStatus.PENDING, owner_token)
            self._records[key] = (record, datetime.now(UTC) + ttl)
            return True

    async def get(self, key: str) -> IdempotencyRecord | None:
        async with self._guard:
            self._purge_expired()
            item = self._records.get(key)
            return item[0] if item is not None else None

    async def complete(
        self,
        key: str,
        *,
        owner_token: str,
        result: Mapping[str, Any],
        ttl: timedelta,
    ) -> bool:
        return await self._finish(
            key,
            owner_token=owner_token,
            result=result,
            ttl=ttl,
            status=IdempotencyStatus.COMPLETED,
        )

    async def fail(
        self,
        key: str,
        *,
        owner_token: str,
        result: Mapping[str, Any],
        ttl: timedelta,
    ) -> bool:
        return await self._finish(
            key,
            owner_token=owner_token,
            result=result,
            ttl=ttl,
            status=IdempotencyStatus.FAILED,
        )

    async def release(self, key: str, *, owner_token: str) -> bool:
        async with self._guard:
            self._purge_expired()
            item = self._records.get(key)
            if item is None or item[0].owner_token != owner_token:
                return False
            if item[0].status != IdempotencyStatus.PENDING:
                return False
            self._records.pop(key, None)
            return True

    async def _finish(
        self,
        key: str,
        *,
        owner_token: str,
        result: Mapping[str, Any],
        ttl: timedelta,
        status: IdempotencyStatus,
    ) -> bool:
        self._validate(key, owner_token, ttl)
        async with self._guard:
            self._purge_expired()
            item = self._records.get(key)
            if item is None or item[0].owner_token != owner_token:
                return False
            record = IdempotencyRecord(key, status, owner_token, result)
            self._records[key] = (record, datetime.now(UTC) + ttl)
            return True

    def _purge_expired(self) -> None:
        now = datetime.now(UTC)
        for key, (_record, expires_at) in tuple(self._records.items()):
            if expires_at <= now:
                self._records.pop(key, None)

    @staticmethod
    def _validate(key: str, owner_token: str, ttl: timedelta) -> None:
        if not key.strip() or not owner_token.strip():
            raise ValueError("key and owner_token must not be empty")
        if ttl <= timedelta(0):
            raise ValueError("ttl must be greater than zero")
