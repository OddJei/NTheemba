from httpx import AsyncClient, Timeout
from .config import Settings


def build_http_client(settings: Settings) -> AsyncClient:
    timeout = Timeout(settings.http_timeout_seconds)
    return AsyncClient(timeout=timeout)
