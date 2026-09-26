"""PostgreSQL connection-pool lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PostgresHealth:
    configured: bool
    connected: bool
    detail: str


class PostgresRuntime:
    """Own one Psycopg asynchronous connection pool."""

    def __init__(
        self,
        dsn: str,
        *,
        min_size: int = 1,
        max_size: int = 10,
        timeout: float = 10.0,
    ) -> None:
        if not dsn.strip():
            raise ValueError("PostgreSQL DSN must not be empty")
        if min_size < 0 or max_size <= 0 or min_size > max_size:
            raise ValueError("invalid PostgreSQL pool sizes")
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._timeout = timeout
        self._pool: Any | None = None

    @property
    def pool(self) -> Any:
        if self._pool is None:
            raise RuntimeError("PostgreSQL runtime has not been opened")
        return self._pool

    async def open(self) -> None:
        if self._pool is not None:
            return
        from psycopg.rows import dict_row
        from psycopg_pool import AsyncConnectionPool

        pool: Any = AsyncConnectionPool(
            conninfo=self._dsn,
            min_size=self._min_size,
            max_size=self._max_size,
            timeout=self._timeout,
            open=False,
            kwargs={"autocommit": False, "row_factory": dict_row},
        )
        await pool.open(wait=True, timeout=self._timeout)
        self._pool = pool

    async def close(self) -> None:
        pool = self._pool
        self._pool = None
        if pool is not None:
            await pool.close()

    async def ping(self) -> bool:
        if self._pool is None:
            return False
        try:
            async with self._pool.connection() as connection:
                result = await connection.execute("SELECT 1 AS ok")
                row = await result.fetchone()
                return bool(row and row["ok"] == 1)
        except Exception:
            return False

    async def health(self) -> PostgresHealth:
        connected = await self.ping()
        return PostgresHealth(
            configured=True,
            connected=connected,
            detail="PostgreSQL query succeeded" if connected else "PostgreSQL query failed",
        )
