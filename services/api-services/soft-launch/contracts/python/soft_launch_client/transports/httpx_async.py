from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

import httpx

from ..client import Transport
from ..models import Request, Response


class HttpxAsyncTransport(Transport):
    def __init__(
        self,
        *,
        base_urls: Mapping[str, str],
        http: httpx.AsyncClient,
    ) -> None:
        self._base_urls = dict(base_urls)
        self._http = http

    async def send(self, request: Request) -> Response:
        if request.service not in self._base_urls:
            raise KeyError(f"No base URL configured for service '{request.service}'")

        base = self._base_urls[request.service].rstrip("/")
        url = f"{base}{request.path}"

        resp = await self._http.request(
            method=request.method,
            url=url,
            params=request.query,
            headers=request.headers,
            json=request.body,
            timeout=request.timeout,
        )

        content_type = resp.headers.get("content-type", "")
        body: Any
        if "application/json" in content_type.lower():
            body = resp.json()
        else:
            body = resp.text

        return Response(status=resp.status_code, headers=dict(resp.headers), body=body)
