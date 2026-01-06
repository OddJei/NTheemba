from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from ..client import Transport
from ..models import Request, Response


Responder = Callable[[Request], Response]


class MockTransport(Transport):
    def __init__(self) -> None:
        self._routes: Dict[Tuple[str, str], Responder] = {}

    def when(self, operation: str, method: str, responder: Responder) -> "MockTransport":
        self._routes[(operation, method.upper())] = responder
        return self

    async def send(self, request: Request) -> Response:
        key = (request.operation, request.method.upper())
        if key not in self._routes:
            return Response(status=501, headers={}, body={"error": "mock_not_configured", "message": f"No mock for {key}"})
        return self._routes[key](request)
