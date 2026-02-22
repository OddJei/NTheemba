from datetime import datetime, timezone
from typing import Dict, Any, Optional
import logging

from httpx import AsyncClient

from ..core.config import get_settings, Settings
from ..models.messages import (
    EnrichedPayload,
    UserContext,
    SessionContext,
    SessionEventIngress,
)
from ..clients import ice_service
from ..services.session_manager import SessionManager
from ..services.errors import PayloadValidationError
from ..services.cache import Cache
from ..services import keys

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
    """Enrich an inbound message by hydrating from ICE first.
    
    New workflow:
    1. Validate & Check (already done) ✓
    2. Hydrate with ICE (to, from, platform only) ← IMMEDIATE
    3. Parse hydration blob into enriched fields ← NEW
    4. Publish enriched
    
    ICE handles: bot lookup, user lookup, session context, capabilities, 
    catalog, service tokens, state resolution — all in one call!
    """
    settings = settings or get_settings()
    cache = Cache(redis, enabled=bool(redis) and settings.cache_enabled)
    
    now = datetime.now(timezone.utc)
    
    # Step 1: Get or create session (lightweight DB operation)
    # We need session_id for hydration
    bot_id = inbound.to  # Use to as temporary bot_id for session creation
    session_id, reactivated = await session_manager.get_or_create_session(
        inbound.from_, bot_id, inbound.meta.platform
    )

    
    # Step 2: ICE Hydration (single call with minimal params)
    # Ice will handle: bot, user, business, catalog, state, service tokens, etc.
    cache_key = keys.hydrated_ingress(session_id)
    hydration_blob = await cache.get_json(cache_key)
    
    if hydration_blob is None:
        # Cache miss - call ICE
        try:
            ice_response = await ice_service.hydrate_session_ingress(
                http_client,
                settings,
                event_id=inbound.request_id,
                session_id=session_id,
                from_number=inbound.from_,
                to_number=inbound.to,
                platform=inbound.meta.platform,
            )
            
            if ice_response and ice_response.get("hydrated"):
                hydration_blob = ice_response.get("session_blob", {})
                if hydration_blob:
                    # Cache the blob for 30 minutes
                    await cache.set_json(cache_key, hydration_blob, ttl_seconds=1800)
        except Exception as exc:
            LOG.warning(f"ICE hydration failed: {exc}, proceeding with minimal context")
            hydration_blob = {}
    
    if hydration_blob is None:
        hydration_blob = {}
    
    # Step 3: Parse hydration blob into enriched fields
    # Extract all context from the single hydrated blob
    user_context = hydration_blob.get("user", {})
    bot_details = hydration_blob.get("bot_details", {})
    business_details = hydration_blob.get("business_details", {})
    owner_details = hydration_blob.get("owner_details", {})
    catalog_context = hydration_blob.get("catalog_context", {})
    metadata = hydration_blob.get("metadata", {})
    
    # Extract from metadata
    service_token = metadata.get("service_token")
    bot_config = metadata.get("bot_config", {}) if isinstance(metadata, dict) else {}
    bot_session = metadata.get("bot_session", {}) if isinstance(metadata, dict) else {}
    if not isinstance(bot_config, dict):
        bot_config = {}
    if not isinstance(bot_session, dict):
        bot_session = {}
    session_state = metadata.get("session_state", "chat")
    expected_action = metadata.get("expected_action", {"action": "show_menu"})
    state_context = metadata.get("state_context", {})
    affiliate_context = metadata.get("affiliate_context")
    
    # Determine session mode from user context
    user_roles = user_context.get("roles", [])
    if not bot_details and isinstance(bot_config, dict) and bot_config:
        bot_details = {
            "id": bot_config.get("bot_id"),
            "bot_type": bot_config.get("bot_type"),
            "business_id": bot_config.get("business_id"),
        }
    bot_type = (
        bot_config.get("bot_type")
        or bot_session.get("bot_type")
        or bot_details.get("bot_type")
        or hydration_blob.get("bot_type")
        or "default"
    )
    
    if bot_type == "custom":
        session_mode = "staff" if "staff" in user_roles else "customer"
    else:
        session_mode = "registered" if set(user_roles).intersection({"msme", "affiliate"}) else "public"
    
    # Prefer bot-session UUID for payloads; error if missing
    external_session_id = bot_session.get("session_id")
    if not external_session_id:
        # Log full inbound metadata to help troubleshooting missing session_id
        try:
            LOG.error(
                "Missing session_id from bot_session metadata",
                extra={
                    "inbound": getattr(inbound, "dict", lambda **kwargs: str(inbound))(),
                    "bot_session": bot_session,
                    "hydration_blob_sample": {k: hydration_blob.get(k) for k in ("user", "bot_details", "metadata")},
                },
            )
        except Exception:
            LOG.exception("failed_logging_missing_session_id")
        raise PayloadValidationError("Missing session_id from bot_session metadata")

    # Build SessionContext from hydration blob
    session_ctx = SessionContext(
        session_id=external_session_id,
        session_mode=session_mode,
        bot_type=bot_type,
        current_node=session_state,
        started_at=now,
        last_active_at=now,
        reset_requested=False,
    )
    
    # Extract allowed actions from expected action
    allowed_actions = []
    if isinstance(expected_action, dict):
        allowed_actions = expected_action.get("allowed_actions", [])
    
    # Build ingress event
    ingress = SessionEventIngress(
        normalized_text=(inbound.message or "").lower().strip(),
        attachments=inbound.attachments or [],
        capabilities=["text"] if inbound.message else [],
        allowed_actions=allowed_actions,
        mode=session_mode,
        mode_id=f"mode_{session_mode}",
        received_at=now,
        user_session={
            "session_id": external_session_id,
            "started_at": now,
            "last_active_at": now,
        },
        previous_events_count=0,
    )
    
    # Step 4: Build enriched payload
    enriched = EnrichedPayload(
        request_id=inbound.request_id,
        event_id=inbound.request_id,
        message=inbound.message,
        to=inbound.to,
        **{"from": inbound.from_},
        timestamp=inbound.timestamp,
        meta={
            "platform": inbound.meta.platform,
            "service_token": service_token,
            "bot": {
                "bot_details": bot_details,
                "business_details": business_details,
                "owner_details": owner_details,
            },
            "user": UserContext(
                id=user_context.get("id"),
                phone=inbound.from_,
                roles=user_roles,
                authenticated=bool(user_context.get("id")),
                business_id=business_details.get("id"),
                locale=user_context.get("locale", "en"),
            ),
            "session": session_ctx,
            "session_state": session_state,
            "expected_action": expected_action,
            "state_context": state_context,
            "catalog_context": catalog_context,
            "affiliate_context": affiliate_context,
            "hydration_blob": hydration_blob,  # Store full blob for downstream
            "previous_events": [],
            "session_event": {
                "event_id": inbound.request_id,
                "started_at": now,
                "ingress": ingress,
            },
        },
    )
    
    # Step 5: Save incoming message after enrichment
    try:
        await ice_service.log_incoming_message(
            http_client,
            settings,
            correlation_id=inbound.request_id,
            session_id=session_id,
            user_phone=inbound.from_,
            bot_phone=inbound.to,
            incoming_message=inbound.message,
            incoming_payload=inbound.dict(by_alias=True),
            incoming_at=inbound.timestamp.isoformat() if inbound.timestamp else None,
        )
    except Exception as exc:
        LOG.warning(f"ICE message log failed: {exc}")

    return enriched
