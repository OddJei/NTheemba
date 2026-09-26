"""Redis-backed conversation session repository."""

from __future__ import annotations

from copy import copy
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

from ntheemba.domain.session import Session
from ntheemba.infrastructure.redis.keys import RedisKeyspace
from ntheemba.infrastructure.serialization import SerializationError, decode_session, encode_session
from ntheemba.ports.sessions import SessionConflictError, SessionKey, SessionRepository


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _clone_with_revision(session: Session, revision: int) -> Session:
    saved = copy(session)
    saved.order_draft = copy(session.order_draft) if session.order_draft else None
    saved.booking_draft = copy(session.booking_draft) if session.booking_draft else None
    saved.recent_history = list(session.recent_history)
    saved.revision = revision
    return saved


class RedisSessionRepository(SessionRepository):
    """Persist versioned JSON sessions with optimistic revision checks."""

    def __init__(
        self,
        client: Any,
        keyspace: RedisKeyspace,
        *,
        session_ttl: timedelta,
        archive_ttl: timedelta,
        clock: Callable[[], datetime] = _utc_now,
        transaction_retries: int = 3,
    ) -> None:
        if session_ttl <= timedelta(0) or archive_ttl <= timedelta(0):
            raise ValueError("session and archive TTLs must be positive")
        if transaction_retries <= 0:
            raise ValueError("transaction_retries must be greater than zero")
        self.client = client
        self.keyspace = keyspace
        self.session_ttl = session_ttl
        self.archive_ttl = archive_ttl
        self.clock = clock
        self.transaction_retries = transaction_retries

    async def load(self, key: SessionKey) -> Session | None:
        payload = await self.client.get(self.keyspace.session(key.business_id, key.customer_id))
        if payload is None:
            return None
        try:
            return decode_session(payload)
        except SerializationError as error:
            raise SerializationError(f"invalid session payload for {key.value}") from error

    async def save(self, session: Session, *, expected_revision: int | None) -> Session:
        redis_key = self.keyspace.session(session.business_id, session.customer_id)
        for attempt in range(self.transaction_retries):
            pipeline: Any = self.client.pipeline(transaction=True)
            try:
                async with pipeline:
                    await pipeline.watch(redis_key)
                    current_payload = await pipeline.get(redis_key)
                    current_revision: int | None = None
                    if current_payload is not None:
                        current_revision = decode_session(current_payload).revision
                    if current_revision != expected_revision:
                        raise SessionConflictError("session revision changed before save")
                    next_revision = (current_revision or 0) + 1
                    saved = _clone_with_revision(session, next_revision)
                    ttl_seconds = self._session_ttl_seconds(saved)
                    pipeline.multi()
                    pipeline.set(redis_key, encode_session(saved), ex=ttl_seconds)
                    await pipeline.execute()
                    return saved
            except Exception as error:
                if type(error).__name__ != "WatchError":
                    raise
                if attempt + 1 >= self.transaction_retries:
                    raise SessionConflictError("session changed during save") from None
                continue
        raise SessionConflictError("session could not be saved")

    async def delete(self, key: SessionKey) -> None:
        await self.client.delete(self.keyspace.session(key.business_id, key.customer_id))

    async def archive(self, session: Session) -> None:
        key = self.keyspace.session_archive(session.conversation_id, session.revision)
        await self.client.set(
            key,
            encode_session(session),
            ex=int(self.archive_ttl.total_seconds()),
        )

    async def ping(self) -> bool:
        try:
            return bool(await self.client.ping())
        except Exception:
            return False

    def _session_ttl_seconds(self, session: Session) -> int:
        remaining = int((session.expires_at - self.clock()).total_seconds())
        configured = int(self.session_ttl.total_seconds())
        return max(1, min(configured, remaining if remaining > 0 else 1))
