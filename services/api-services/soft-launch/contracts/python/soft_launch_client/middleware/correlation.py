from __future__ import annotations

import uuid

from ..client import Middleware
from ..models import Request, Response


class CorrelationMiddleware(Middleware):
    header_name = "X-Correlation-Id"

    async def handle(self, request: Request, next_call) -> Response:
        correlation_id = request.headers.get(self.header_name) or request.context.get("correlation_id")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        request.context["correlation_id"] = correlation_id
        request.headers[self.header_name] = correlation_id
        return await next_call(request)
