import asyncio
from datetime import datetime

from app.models.messages import InboundMessage


class FakeRedis:
    def __init__(self):
        self._kv = {}

    async def get(self, key: str):
        return self._kv.get(key)

    async def set(self, key: str, value: str, ex=None, nx=False):
        if nx and key in self._kv:
            return None
        self._kv[key] = value
        return True


class DummySessionManager:
    def __init__(self, session_id="sess_test"):
        self._session_id = session_id

    async def get_or_create_session(self, user_phone: str, bot_id: str, platform: str):
        return self._session_id, False


def test_hydrate_first_sets_canonical_session_context(monkeypatch):
    from app.ingress import enricher
    from app.core.config import Settings
    from app.services import keys

    # Minimal fake upstream client calls (not used when allow_http_fallback=False)
    async def fake_get_bot(client, settings, phone):
        raise AssertionError("should not call bot service when fallback disabled")

    async def fake_lookup_user(client, settings, phone, business_id=None):
        raise AssertionError("should not call auth service when fallback disabled")

    async def fake_fetch_caps(client, settings, mode_name):
        raise AssertionError("should not call capabilities service when fallback disabled")

    monkeypatch.setattr("app.clients.bot_service.get_bot_by_phone", fake_get_bot)
    monkeypatch.setattr("app.clients.auth_service.lookup_user", fake_lookup_user)
    monkeypatch.setattr("app.clients.capability_service.fetch_capabilities", fake_fetch_caps)

    async def fake_preload_session_context(
        client,
        settings,
        *,
        event_id,
        session_id,
        user_phone,
        bot_id,
        platform,
        bot_type,
        business_id=None,
        required_blobs=None,
    ):
        # Return a dict like ICE would.
        return {"schema_version": "v1", "session_id": session_id, "intent_required": True}

    monkeypatch.setattr("app.clients.ice_service.preload_session_context", fake_preload_session_context)

    inbound = InboundMessage.parse_obj(
        {
            "request_id": "req_test",
            "message": "Hello",
            "to": "ntb_default",
            "from": "097xxxxxxx",
            "timestamp": datetime.utcnow().isoformat(),
            "meta": {"platform": "wa"},
        }
    )

    redis = FakeRedis()
    session_manager = DummySessionManager(session_id="sess_test")

    settings = Settings(
        ingress_hydrate_first=True,
        enrich_allow_fallback_http=False,
        ice_service_url="http://ice.local",
    )

    enriched = asyncio.run(enricher.enrich_inbound(inbound, http_client=None, redis=redis, session_manager=session_manager, settings=settings))

    # Ensure meta contains hydrated session_context
    assert isinstance(enriched.meta, dict)
    assert enriched.meta["session_context"].get("session_id") == "sess_test"

    # Ensure canonical key is written
    canon_key = keys.session_context("sess_test")
    assert asyncio.run(redis.get(canon_key)) is not None
