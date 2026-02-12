from __future__ import annotations

import httpx

from ..adapters.base import ProviderAdapter
from ..adapters.http_adapter import HttpProviderAdapter
from ..adapters.stub_adapter import StubProviderAdapter


def get_adapter(provider: str, http_client: httpx.AsyncClient) -> ProviderAdapter:
    provider = (provider or "").strip().lower()
    if provider == "http":
        return HttpProviderAdapter(http_client)

    # wa/sms/etc not implemented yet -> stub
    return StubProviderAdapter()
