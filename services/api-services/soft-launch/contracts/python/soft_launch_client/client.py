from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Dict, Iterable, Mapping, Optional

from .models import Headers, OperationSpec, Request, Response

NextCall = Callable[[Request], Awaitable[Response]]


class Transport:
    async def send(self, request: Request) -> Response:
        raise NotImplementedError


class Middleware:
    async def handle(self, request: Request, next_call: NextCall) -> Response:
        return await next_call(request)


class AsyncServiceClient:
    def __init__(
        self,
        operation_map: Mapping[str, OperationSpec],
        transport: Transport,
        middlewares: Optional[Iterable[Middleware]] = None,
    ) -> None:
        self._operation_map = dict(operation_map)
        self._transport = transport
        self._middlewares = list(middlewares or [])

    async def call(
        self,
        operation: str,
        *,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Headers] = None,
        query: Optional[Mapping[str, str]] = None,
        timeout: float = 10.0,
        path_params: Optional[Mapping[str, str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Response:
        if operation not in self._operation_map:
            raise KeyError(f"Unknown operation: {operation}")

        spec = self._operation_map[operation]
        path = spec.path.format(**(path_params or {}))

        req = Request(
            service=spec.service,
            operation=operation,
            method=spec.method,
            path=path,
            query=query,
            headers=dict(headers or {}),
            body=body,
            timeout=timeout,
            context=dict(context or {}),
        )

        req.context.setdefault("correlation_id", req.headers.get("X-Correlation-Id") or str(uuid.uuid4()))

        async def invoke_transport(r: Request) -> Response:
            return await self._transport.send(r)

        next_call: NextCall = invoke_transport
        for mw in reversed(self._middlewares):
            prev = next_call

            async def wrapped(r: Request, _mw: Middleware = mw, _prev: NextCall = prev) -> Response:
                return await _mw.handle(r, _prev)

            next_call = wrapped

        return await next_call(req)
