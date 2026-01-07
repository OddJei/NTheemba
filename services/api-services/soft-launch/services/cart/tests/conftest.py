from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


class _FakeResponse:
    def __init__(self, status_code: int, json_data: dict | None = None):
        self.status_code = int(status_code)
        self._json_data = json_data or {}

    def json(self) -> dict:
        return dict(self._json_data)


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, headers: dict | None = None):
        # URL: http://.../inventory/{variant_id}
        parts = url.rstrip("/").split("/")
        if len(parts) >= 2 and parts[-2] == "inventory":
            variant_id = parts[-1]
            inv = _INVENTORY_STATE.get(variant_id)
            if not inv:
                return _FakeResponse(404, {"detail": "inventory_not_found"})
            return _FakeResponse(200, inv)
        return _FakeResponse(404, {"detail": "not_found"})

    async def post(self, url: str, json: dict | None = None, headers: dict | None = None):
        # URL: http://.../inventory/update
        if url.rstrip("/").endswith("/inventory/update"):
            payload = json or {}
            variant_id = payload.get("variant_id")
            delta = int(payload.get("delta", 0))
            reserved_delta = int(payload.get("reserved_delta", 0) or 0)

            inv = _INVENTORY_STATE.setdefault(
                variant_id,
                {"variant_id": variant_id, "stock_level": 100, "reserved": 0, "threshold": 0, "updated_at": "2026-01-01T00:00:00Z"},
            )

            current_stock = int(inv.get("stock_level", 0))
            current_reserved = int(inv.get("reserved", 0))
            new_stock = current_stock + delta
            new_reserved = current_reserved + reserved_delta

            if new_stock < 0 or new_reserved < 0 or new_reserved > new_stock:
                return _FakeResponse(409, {"detail": "insufficient_stock"})

            inv["stock_level"] = int(new_stock)
            inv["reserved"] = int(new_reserved)
            return _FakeResponse(200, inv)

        return _FakeResponse(404, {"detail": "not_found"})


_INVENTORY_STATE: dict[str, dict] = {}


@pytest.fixture(scope="session")
def service_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def _configure_test_db(service_root: Path) -> None:
    tmp = tempfile.NamedTemporaryFile(prefix="cart_service_test_", suffix=".db", delete=False)
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp.name}"
    sys.path.insert(0, str(service_root))


@pytest.fixture()
def client() -> TestClient:
    # Patch httpx.AsyncClient before importing app, so cart inventory calls are mocked.
    import httpx

    httpx.AsyncClient = _FakeAsyncClient  # type: ignore[assignment]

    from src.app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def inventory_state() -> dict[str, dict]:
    _INVENTORY_STATE.clear()
    _INVENTORY_STATE["v-1"] = {"variant_id": "v-1", "stock_level": 100, "reserved": 0, "threshold": 0, "updated_at": "2026-01-01T00:00:00Z"}
    return _INVENTORY_STATE
