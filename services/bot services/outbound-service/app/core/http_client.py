from __future__ import annotations

import httpx

from .config import Settings


def build_http_client(settings: Settings) -> httpx.AsyncClient:
    timeout = httpx.Timeout(settings.http_timeout_seconds)
    return httpx.AsyncClient(timeout=timeout)
