import asyncio
import os
import sys

# Ensure the repository root (contains `libs/`) is importable so helpers can import `libs.*`
cur = os.path.abspath(os.path.dirname(__file__))
root = cur
while not os.path.isdir(os.path.join(root, "libs")):
    parent = os.path.abspath(os.path.join(root, ".."))
    if parent == root:
        break
    root = parent
if root not in sys.path:
    sys.path.insert(0, root)
# Also ensure the ICE-service app package is importable (this dir's parent)
ice_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ice_root not in sys.path:
    sys.path.insert(0, ice_root)

from app.blob_builders import build_business_blob
from app.helpers import service_helpers


def test_build_business_blob(monkeypatch):
    async def fake_get_business_by_id(business_id: str):
        return {"profile": {"id": business_id, "owner_phone": "+260900000001"}, "policies": {"p": True}}

    async def fake_get_business_by_phone(phone: str):
        return {"id": "biz_by_phone", "name": "BizCo", "owner_phone": phone}

    async def fake_get_user_by_phone(phone: str):
        return {"id": "user1", "phone": phone, "name": "Owner"}

    async def fake_get_service_token(business_id: str):
        return "svc-token-xyz"

    monkeypatch.setattr(service_helpers, "get_business_by_id", fake_get_business_by_id)
    monkeypatch.setattr(service_helpers, "get_business_by_phone", fake_get_business_by_phone)
    monkeypatch.setattr(service_helpers, "get_user_by_phone", fake_get_user_by_phone)
    monkeypatch.setattr(service_helpers, "get_service_token", fake_get_service_token)

    async def fake_persist_and_cache_blob(key: str, blob: dict, session_id: str = None, ttl: int = 3600):
        return {"cached": True, "persisted": True}

    monkeypatch.setattr(service_helpers, "persist_and_cache_blob", fake_persist_and_cache_blob)

    res = asyncio.run(build_business_blob(phone="+260900000001", business_id="biz1", session_id="sess1"))

    assert res["profile"]["id"] == "biz1"
    assert isinstance(res["owners"], list) and res["owners"]
    assert res["owners"][0]["phone"] == "+260900000001"
    assert res["service_token"] == "svc-token-xyz"
    assert res["_meta"]["business_id_used"] == "biz1"


def test_build_business_blob_returns_db_fresh(monkeypatch):
    """If DB has a fresh hydrated blob row for the redis key, it should be returned unchanged."""
    async def fake_get_hydrated_blob(key: str):
        from types import SimpleNamespace
        from datetime import datetime, timezone

        blob = {"profile": {"id": "from_db"}, "_meta": {"source": "db"}}
        row = SimpleNamespace()
        row.blob = blob
        row.updated_at = datetime.now(timezone.utc)
        return row

    # Monkeypatch the repository classes used by the builder when available
    import app.state.repository as repo_mod

    class FakeRepo:
        def __init__(self, db):
            pass

        async def get_hydrated_blob(self, key: str):
            return await fake_get_hydrated_blob(key)

    def fake_async_session_local():
        class Ctx:
            async def __aenter__(self):
                return None

            async def __aexit__(self, exc_type, exc, tb):
                return False

        return Ctx()

    monkeypatch.setattr(repo_mod, "IceRepository", FakeRepo)
    monkeypatch.setattr(repo_mod, "AsyncSessionLocal", fake_async_session_local)

    res = asyncio.run(build_business_blob(phone="+260900000001", business_id="biz1", session_id=None))
    assert res.get("profile", {}).get("id") == "from_db"


def test_build_customer_blob_registers_when_no_user(monkeypatch):
    # ensure msme lookup returns empty
    async def fake_get_user_by_phone(phone: str):
        return {}

    async def fake_ensure_user_exists(phone: str, *, display_name: str = None):
        return {"id": "newuser1", "phone": phone, "name": "unknown", "created_placeholder": True}

    monkeypatch.setattr(service_helpers, "get_user_by_phone", fake_get_user_by_phone)
    monkeypatch.setattr(service_helpers, "ensure_user_exists", fake_ensure_user_exists)

    from app.blob_builders import build_customer_blob

    res = asyncio.run(build_customer_blob(phone="+260900000002", session_id=None))
    assert res["profile"]["id"] == "newuser1"
    assert res["_meta"]["redis_key"] == "customer:+260900000002"
