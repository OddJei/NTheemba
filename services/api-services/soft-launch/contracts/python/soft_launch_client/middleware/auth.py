from __future__ import annotations

from typing import Awaitable, Callable, Optional

from ..client import Middleware
from ..models import Request, Response


TokenProvider = Callable[[Request], Awaitable[str] | str]


class AuthMiddleware(Middleware):
    header_name = "Authorization"

    def __init__(self, token_provider: TokenProvider, *, scheme: str = "Bearer") -> None:
        self._token_provider = token_provider
        self._scheme = scheme

    async def handle(self, request: Request, next_call) -> Response:
        token = self._token_provider(request)
        if hasattr(token, "__await__"):
            token = await token  # type: ignore[assignment]
        if token:
            request.headers[self.header_name] = f"{self._scheme} {token}"
        return await next_call(request)
