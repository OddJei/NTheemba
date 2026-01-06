from __future__ import annotations

import logging
import time

from ..client import Middleware
from ..models import Request, Response


class ObservabilityMiddleware(Middleware):
    def __init__(self, *, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("soft_launch_client")

    async def handle(self, request: Request, next_call) -> Response:
        start = time.perf_counter()
        try:
            resp = await next_call(request)
            return resp
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            correlation_id = request.headers.get("X-Correlation-Id") or request.context.get("correlation_id")
            self._logger.info(
                "service_call service=%s operation=%s method=%s path=%s elapsed_ms=%.2f correlation_id=%s",
                request.service,
                request.operation,
                request.method,
                request.path,
                elapsed_ms,
                correlation_id,
            )
