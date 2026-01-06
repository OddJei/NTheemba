from __future__ import annotations

import asyncio

import httpx

from ..client import Middleware
from ..models import Request, Response


class RetryMiddleware(Middleware):
    def __init__(
        self,
        *,
        max_attempts: int = 3,
        base_delay_seconds: float = 0.25,
        retry_statuses: tuple[int, ...] = (502, 503, 504),
    ) -> None:
        self._max_attempts = max_attempts
        self._base_delay_seconds = base_delay_seconds
        self._retry_statuses = retry_statuses

    async def handle(self, request: Request, next_call) -> Response:
        attempt = 0
        last_exc: Exception | None = None

        while attempt < self._max_attempts:
            attempt += 1
            try:
                resp = await next_call(request)
                if resp.status in self._retry_statuses and attempt < self._max_attempts:
                    await asyncio.sleep(self._base_delay_seconds * (2 ** (attempt - 1)))
                    continue
                return resp
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt >= self._max_attempts:
                    raise
                await asyncio.sleep(self._base_delay_seconds * (2 ** (attempt - 1)))

        if last_exc:
            raise last_exc

        return await next_call(request)
