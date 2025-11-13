from datetime import datetime, timezone
from typing import Dict, Any, Tuple
import logging

from httpx import AsyncClient

from ..core.config import get_settings, Settings
from ..models.messages import (
    EnrichedPayload,
    UserContext,
    SessionContext,
    SessionEvent,
    SessionEventIngress,
)
from ..clients import bot_service, auth_service, capability_service
from ..services.session_manager import SessionManager

LOG = logging.getLogger("bot-ingress.enricher")


MODE_NAME_MAP = {
    "public": "public",
    "registered": "registered_user",
    "customer": "customer",
    "staff": "staff_only",
}


async def enrich_inbound(
    inbound: Any,
    http_client: AsyncClient,
    redis,
    session_manager: SessionManager,
    settings: Settings = None,
) -> EnrichedPayload:
    """Enrich an inbound message into an EnrichedPayload.

    This follows the payload_story_public steps: bot lookup, user lookup, capabilities,
    session upsert/reactivate, and building the enriched payload structure.
    """
    settings = settings or get_settings()

    # 1) Resolve bot
    bot_info = await bot_service.get_bot_by_phone(http_client, settings, inbound.to)
    if not bot_info:
        # Treat missing as default bot with minimal details
        bot_type = "default"
        bot_details = {}
        business_details = {}
        owner_details = {}
    else:
        bot_type = bot_info.get("bot_type", "default")
        bot_details = bot_info.get("bot_details", {})
        business_details = bot_info.get("business_details", {})
        owner_details = bot_info.get("owner_details", {})

    # 2) Resolve user and session_mode
    if bot_type == "custom":
        business_id = business_details.get("id")
        user_info = await auth_service.lookup_user(http_client, settings, inbound.from_, business_id)
        roles = user_info.get("roles", []) if user_info else []
        session_mode = "staff" if "staff" in roles else "customer"
        user_ctx = UserContext(
            id=user_info.get("id") if user_info else None,
            phone=inbound.from_,
            roles=roles or ["customer"],
            authenticated=bool(user_info),
            business_id=business_id,
            locale=(user_info.get("locale") if user_info else "en"),
        )
    else:
        user_info = await auth_service.lookup_user(http_client, settings, inbound.from_)
        roles = user_info.get("roles", []) if user_info else []
        session_mode = "registered" if set(roles).intersection({"msme", "affiliate"}) else "public"
        user_ctx = UserContext(
            id=user_info.get("id") if user_info else None,
            phone=inbound.from_,
            roles=roles or ["public"],
            authenticated=bool(user_info),
            business_id=None,
            locale=(user_info.get("locale") if user_info else "en"),
        )

    # 3) Capabilities
    mode_name = MODE_NAME_MAP.get(session_mode, "public")
    try:
        caps_resp = await capability_service.fetch_capabilities(http_client, settings, mode_name)
    except Exception:
        LOG.exception("failed to fetch capabilities for mode %s", mode_name)
        caps_resp = {"capabilities": [], "mode": {"id": f"mode_{mode_name}"}}

    allowed_actions = [c.get("action") for c in caps_resp.get("capabilities", []) if c.get("action")]

    # 4) Session (get or create)
    bot_id = bot_details.get("id", "default_bot")
    session_id, reactivated = await session_manager.get_or_create_session(inbound.from_, bot_id, inbound.meta.platform)

    now = datetime.now(timezone.utc)

    # 5) Build enriched meta/session_event
    ingress = SessionEventIngress(
        normalized_text=(inbound.message or "").lower().strip(),
        attachments=inbound.attachments or [],
        capabilities=["text"] if inbound.message else [],
        allowed_actions=allowed_actions,
        mode=session_mode,
        mode_id=caps_resp.get("mode", {}).get("id", f"mode_{mode_name}"),
        received_at=now,
        user_session={
            "session_id": session_id,
            "started_at": now,
            "last_active_at": now,
        },
        previous_events_count=0,
    )

    session_ctx = SessionContext(
        session_id=session_id,
        session_mode=session_mode,
        bot_type=bot_type,
        current_node=None,
        started_at=now,
        last_active_at=now,
        reset_requested=False,
    )

    # event_id will be assigned later in the pipeline; set to None for now
    enriched = EnrichedPayload(
        request_id=inbound.request_id,
        event_id=None,
        message=inbound.message,
        to=inbound.to,
        **{"from": inbound.from_},
        timestamp=inbound.timestamp,
        meta={
            "platform": inbound.meta.platform,
            "bot": {
                "bot_details": bot_details,
                "business_details": business_details,
                "owner_details": owner_details,
            },
            "user": user_ctx,
            "session": session_ctx,
            "previous_events": [],
            "session_event": {
                "event_id": None,
                "started_at": now,
                "ingress": ingress,
            },
        },
    )

    return enriched
