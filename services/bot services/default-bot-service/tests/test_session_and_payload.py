from datetime import datetime, timedelta
import pytest

from models.session_context import SessionContext, UserContext, TreeState, NodeState, NodeStatus, SessionStatus
from models.payload import BotPayload, MetaInfo, SessionInfo, BotInfo, UserInfo, CurrentEvent


def test_session_basic_lifecycle():
    now = datetime.now()
    session = SessionContext(
        session_id="s1",
        user_id="u1",
        status=SessionStatus.ACTIVE,
        created_at=now,
        last_activity=now,
        expires_at=now + timedelta(seconds=3600),
        user_context=UserContext()
    )

    assert session.is_active()
    session.extend_session(10)
    assert session.expires_at > now

    session.add_cart_item({"id": "p1", "qty": 1})
    assert len(session.user_context.cart_items) == 1


def test_payload_properties():
    bot = BotInfo(bot_id="b1", is_default=True)
    user = UserInfo(user_id="u1", role="msme")
    sess = SessionInfo(session_id="s1", session_mode="registered", bot_type="default")
    current_event = CurrentEvent(event_id="e1", timestamp="t", status="ok", current_node="root", possible_next_nodes={})
    meta = MetaInfo(platform="wa", bot=bot, user=user, session=sess, current_event=current_event)
    payload = BotPayload(request_id="r1", message="hi", to="me", from_="you", meta=meta)

    assert payload.session_mode == "registered"
    assert payload.is_msme_user
