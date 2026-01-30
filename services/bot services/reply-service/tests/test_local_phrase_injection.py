from app.services.renderer import ReplyRenderer
from app.core.config import get_settings
from app.models import ReplyRequest


def test_local_phrase_injection():
    settings = get_settings()
    r = ReplyRenderer(settings)
    # Create a multi-sentence draft to allow insertion
    draft = (
        "Your order has been updated. Please review the items. We will notify you when ready. "
        "If you want to checkout, reply CONFIRM ORDER."
    )
    req = ReplyRequest(event_id="e1", session_id="s1", text=draft, meta={"business_name": "Kitwe Solar"})
    out = r._ensure_warmth_and_local_phrases(draft)
    # Expect at least one local phrase present
    assert any(p in out for p in ["Zikomo", "Twalumba", "Muli shani", "Mukwai"]) , out
    # Ensure persona prefix is not removed by post-processing (prefixing occurs earlier normally)
    # For this test we only check local phrase injection
