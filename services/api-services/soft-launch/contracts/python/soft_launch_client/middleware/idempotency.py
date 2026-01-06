from __future__ import annotations

import uuid

from ..client import Middleware
from ..models import Request, Response


class IdempotencyMiddleware(Middleware):
    header_name = "X-Idempotency-Key"

    def __init__(self, *, enabled_methods: tuple[str, ...] = ("POST", "PUT")) -> None:
        self._enabled_methods = tuple(m.upper() for m in enabled_methods)

    async def handle(self, request: Request, next_call) -> Response:
        if request.method.upper() in self._enabled_methods:
            if self.header_name not in request.headers:
                request.headers[self.header_name] = request.context.get("idempotency_key") or str(uuid.uuid4())
        return await next_call(request)
