import asyncio
from datetime import datetime

from app.models.messages import InboundMessage


class DummySessionManager:
    def __init__(self, session_id="sess_test"):
        self._session_id = session_id

    async def ensure_first_processing(self, request_id: str):
        return True

    async def get_or_create_session(self, user_phone: str, bot_id: str, platform: str):
        return self._session_id, False


async def _run_enricher(monkeypatch):
    from app.ingress import enricher

    # patch client calls
    async def fake_get_bot(client, settings, phone):
        return {"bot_type": "default", "bot_details": {"id": "default_bot"}, "business_details": {}, "owner_details": {}}

    async def fake_lookup_user(client, settings, phone, business_id=None):
        return {"id": "usr_1", "roles": ["public"], "locale": "en-ZM"}

    async def fake_fetch_caps(client, settings, mode_name):
        return {"mode": {"id": "mode_public"}, "capabilities": [{"action": "browse_products"}, {"action": "place_orders"}]}

    monkeypatch.setattr("app.clients.bot_service.get_bot_by_phone", fake_get_bot)
    monkeypatch.setattr("app.clients.auth_service.lookup_user", fake_lookup_user)
    monkeypatch.setattr("app.clients.capability_service.fetch_capabilities", fake_fetch_caps)

    inbound = InboundMessage.parse_obj({
        "request_id": "req_test",
        "message": "Hello",
        "to": "ntb_default",
        "from": "097xxxxxxx",
        "timestamp": datetime.utcnow().isoformat(),
        "meta": {"platform": "wa"},
    })

    settings = None
    redis = None
    session_manager = DummySessionManager()

    enriched = await enricher.enrich_inbound(inbound, None, redis, session_manager, settings)
    return enriched


def test_enricher_basic(monkeypatch):
    enriched = asyncio.run(_run_enricher(monkeypatch))
    # meta contains model instances for session and ingress; handle both dict and model cases
    session_val = enriched.meta.get("session")
    if hasattr(session_val, "session_id"):
        session_id = session_val.session_id
    else:
        session_id = session_val["session_id"]

    assert session_id == "sess_test"

    ingress_val = enriched.meta["session_event"]["ingress"]
    if hasattr(ingress_val, "allowed_actions"):
        allowed = ingress_val.allowed_actions
    else:
        allowed = ingress_val["allowed_actions"]

    # allowed_actions should include mapped capabilities
    assert "browse_products" in allowed
