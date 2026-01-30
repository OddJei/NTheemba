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
from ..clients import ice_service
from ..services.session_manager import SessionManager
from ..services.cache import (
    Cache,
    cache_key_bot,
    cache_key_user,
    cache_key_capabilities,
    cache_key_session_context,
)
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
    """Enrich an inbound message into an EnrichedPayload.

    This follows the payload_story_public steps: bot lookup, user lookup, capabilities,
    session upsert/reactivate, and building the enriched payload structure.
    """
    settings = settings or get_settings()
    cache = Cache(redis, enabled=bool(redis) and settings.cache_enabled, read_only=getattr(settings, "redis_kv_read_only", False))

    allow_http_fallback = bool(getattr(settings, "enrich_allow_fallback_http", True))

    # 1) Resolve bot (cache-first)
    bot_cache_key = cache_key_bot(inbound.to)
    # If ICE is configured and hydrate-first mode is enabled, ask ICE to preload
    # backend blobs (including bot_core) so we can avoid calling HTTP backends.
    if settings.ice_service_url and getattr(settings, "ingress_hydrate_first", False):
        try:
            await ice_service.preload_session_context(
                http_client,
                settings,
                event_id=inbound.request_id,
                session_id="",
                user_phone=inbound.from_,
                bot_id=inbound.to,
                platform=inbound.meta.platform,
                bot_type="unknown",
                required_blobs=["bot_core", "bot_meta", "session_context"],
            )
        except Exception:
            LOG.debug("ICE preload for bot blobs failed or returned nothing")
    bot_info = await cache.get_json(bot_cache_key)
    if bot_info is None:
        if allow_http_fallback:
            bot_info = await bot_service.get_bot_by_phone(http_client, settings, inbound.to)
            if bot_info is not None:
                await cache.set_json(bot_cache_key, bot_info, ttl_seconds=settings.bot_cache_ttl_seconds)
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

    # 2) Resolve user and session_mode (cache-first)
    if bot_type == "custom":
        business_id = business_details.get("id")
        user_cache_key = cache_key_user(inbound.from_, business_id)
        user_info = await cache.get_json(user_cache_key)
        if user_info is None:
            if allow_http_fallback:
                user_info = await auth_service.lookup_user(http_client, settings, inbound.from_, business_id)
                if user_info is not None:
                    await cache.set_json(user_cache_key, user_info, ttl_seconds=settings.user_cache_ttl_seconds)
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
        user_cache_key = cache_key_user(inbound.from_, None)
        user_info = await cache.get_json(user_cache_key)
        if user_info is None:
            if allow_http_fallback:
                user_info = await auth_service.lookup_user(http_client, settings, inbound.from_)
                if user_info is not None:
                    await cache.set_json(user_cache_key, user_info, ttl_seconds=settings.user_cache_ttl_seconds)
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

    # 3) Capabilities (cache-first)
    mode_name = MODE_NAME_MAP.get(session_mode, "public")
    try:
        caps_cache_key = cache_key_capabilities(mode_name)
        caps_resp = await cache.get_json(caps_cache_key)
        if caps_resp is None:
            if allow_http_fallback:
                caps_resp = await capability_service.fetch_capabilities(http_client, settings, mode_name)
                await cache.set_json(caps_cache_key, caps_resp, ttl_seconds=settings.capabilities_cache_ttl_seconds)
            else:
                caps_resp = {"capabilities": [], "mode": {"id": f"mode_{mode_name}"}}
    except Exception:
        LOG.exception("failed to fetch capabilities for mode %s", mode_name)
        caps_resp = {"capabilities": [], "mode": {"id": f"mode_{mode_name}"}}

    allowed_actions = [c.get("action") for c in caps_resp.get("capabilities", []) if c.get("action")]

    # 4) Session (get or create)
    bot_id = bot_details.get("id", "default_bot")
    session_id, reactivated = await session_manager.get_or_create_session(inbound.from_, bot_id, inbound.meta.platform)

    # 4b) Session context preload (cache-first, ICE on miss)
    # Prefer canonical key for hydrated session context, but keep backward-compat.
    session_context_key = keys.session_context(session_id)
    legacy_session_context_key = cache_key_session_context(session_id)
    session_context = await cache.get_json(session_context_key)
    if session_context is None:
        session_context = await cache.get_json(legacy_session_context_key)
    if session_context is None:
        # Hydrate-first mode: best-effort ICE call that should populate Redis JSONB blobs.
        # We dedupe concurrent cache misses with a short-lived NX lock and apply a negative cache on failure.
        if getattr(settings, "ingress_hydrate_first", False):
            lock_key = keys.lock_hydrate(session_id)
            neg_key = keys.neg_hydrate(session_id)
            if not await cache.is_negative(neg_key):
                acquired = await cache.acquire_lock(lock_key, ttl_seconds=getattr(settings, "hydrate_lock_ttl_seconds", 20))
                if acquired:
                    required_blobs = [
                        # session/user
                        "session",
                        "session_context",
                        "order_draft",
                        # bot
                        "bot_core",
                        "bot_owner",
                        "catalog_index",
                        "catalog_product",
                        "bot_policy",
                        "bot_routing",
                        "bot_config",
                        "bot_templates",
                        "bot_flow",
                    ]
                    preloaded = await ice_service.preload_session_context(
                        http_client,
                        settings,
                        event_id=inbound.request_id,
                        session_id=session_id,
                        user_phone=inbound.from_,
                        bot_id=bot_id,
                        platform=inbound.meta.platform,
                        bot_type=bot_type,
                        business_id=(business_details.get("id") if bot_type == "custom" else None),
                        required_blobs=required_blobs,
                    )
                    if preloaded is not None:
                        session_context = preloaded
                        await cache.set_json(session_context_key, session_context, ttl_seconds=settings.session_context_ttl_seconds)
                    else:
                        await cache.set_negative(neg_key, ttl_seconds=getattr(settings, "hydrate_negative_ttl_seconds", 30))
        else:
            # Optional ICE preload on cache miss (legacy behavior)
            preloaded = await ice_service.preload_session_context(
                http_client,
                settings,
                event_id=inbound.request_id,
                session_id=session_id,
                user_phone=inbound.from_,
                bot_id=bot_id,
                platform=inbound.meta.platform,
                bot_type=bot_type,
                business_id=(business_details.get("id") if bot_type == "custom" else None),
            )
            if preloaded is not None:
                session_context = preloaded
                # Write both canonical and legacy keys during transition.
                await cache.set_json(session_context_key, session_context, ttl_seconds=settings.session_context_ttl_seconds)
                await cache.set_json(legacy_session_context_key, session_context, ttl_seconds=settings.session_context_ttl_seconds)

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
            # Backwards-compatible embedded small bot/user/session snapshots
            "bot": {"bot_details": bot_details} if not getattr(settings, "ingress_use_refs", False) else {},
            "user": user_ctx,
            # session snapshot always included for routing
            "session": session_ctx,
            # session_context is the hydrated blob (may be {})
            "session_context": session_context or {},
            "previous_events": [],
            "session_event": {"event_id": None, "started_at": now, "ingress": ingress},
        },
    )

    # If configured, populate canonical refs instead of embedding large blobs
    if getattr(settings, "ingress_use_refs", False):
        enriched.meta = dict(enriched.meta or {})
        # Bot ref
        bot_ref = {
            "key": keys.bot_core(bot_details.get("id") or "default_bot"),
            "id": bot_details.get("id") or "default_bot",
            "schema_version": bot_details.get("schema_version") or "v1",
            "snapshot": {"bot_type": bot_type, "primary_lane": bot_details.get("routing", {}).get("primary_lane")},
        }
        enriched.meta["bot_ref"] = bot_ref

        # Session ref + small inline snapshot
        session_snapshot = {"session_id": session_id, "started_at": now.isoformat(), "last_active_at": now.isoformat()}
        session_ref = {"key": keys.session_context(session_id), "id": session_id, "schema_version": (session_context or {}).get("schema_version", "v1"), "snapshot": {"session_mode": session_mode}}
        enriched.meta["session_ref"] = session_ref
        enriched.meta["session_snapshot"] = session_snapshot

    return enriched
