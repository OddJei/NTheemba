from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.helpers import service_helpers
import os
import time
import json

try:
    import redis.asyncio as aioredis  # type: ignore
except Exception:
    aioredis = None

logger = logging.getLogger(__name__)


async def build_business_blob(
    *,
    phone: Optional[str] = None,
    business_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build the `business` hydrated blob.

    - Attempts authority lookup by `business_id` (preferred) or `phone`.
    - Includes: profile, policies, owners (user objects), and a service token.
    - Returns a dict suitable for storing under `oob.meta.hydrated_blobs['business']`.
    """
    out: Dict[str, Any] = {"profile": {}, "policies": {}, "owners": [], "service_token": None, "_meta": {"ttl": 3600}}

    # Try Redis cache first (best-effort; optional dependency).
    redis_url = os.environ.get("REDIS_URL")
    redis_client = None
    cache_key = None
    try:
        if aioredis and (business_id or phone) and redis_url:
            redis_client = aioredis.from_url(redis_url, decode_responses=True)
            if business_id:
                cache_key = f"business_blob:{business_id}"
            else:
                cache_key = f"business_blob:phone:{phone}"
            cached = await redis_client.get(cache_key)
            if cached:
                try:
                    parsed = json.loads(cached)
                    # consider stale if older than 1 day
                    cached_at = parsed.get("_meta", {}).get("cached_at") or parsed.get("_meta", {}).get("fetched_at")
                    if cached_at:
                        age = time.time() - float(cached_at)
                        if age < 86400:  # 1 day
                            return parsed
                except Exception:
                    logger.exception("failed_parsing_cached_business_blob")
    except Exception:
        logger.exception("redis_cache_check_failed")

    # Compose the canonical redis key we use for hydrated blobs (phone preferred)
    if phone:
        redis_key = f"business:{phone}"
    else:
        redis_key = f"business:{business_id}"

    # Check DB-persisted hydrated blob for freshness before rebuilding
    try:
        from app.state.repository import AsyncSessionLocal, IceRepository
        try:
            async with AsyncSessionLocal() as db:
                repo = IceRepository(db)
                row = await repo.get_hydrated_blob(redis_key)
                if row:
                    # row.updated_at is a datetime
                    try:
                        updated_ts = row.updated_at.timestamp()
                        age = time.time() - updated_ts
                        if age < out["_meta"].get("ttl", 3600):
                            return row.blob
                    except Exception:
                        logger.exception("error_checking_hydrated_blob_age")
        except Exception:
            # DB unavailable or repo call failed — continue to rebuild
            logger.debug("hydrated_blob db check unavailable")
    except Exception:
        # repository package not present or import failed
        pass

    try:
        # 1) Fetch business profile + policies by id when available
        if business_id:
            try:
                biz = await service_helpers.get_business_by_id(business_id)
            except Exception:
                logger.exception("get_business_by_id failed")
                biz = {}
            if isinstance(biz, dict):
                out["profile"] = biz.get("profile") or {}
                out["policies"] = biz.get("policies") or {}

        # 2) If still missing, try lookup by phone
        if (not out["profile"] or not business_id) and phone:
            try:
                biz_by_phone = await service_helpers.get_business_by_phone(phone)
            except Exception:
                logger.exception("get_business_by_phone failed")
                biz_by_phone = {}
            if isinstance(biz_by_phone, dict) and biz_by_phone:
                out["profile"] = out["profile"] or biz_by_phone
                business_id = business_id or biz_by_phone.get("id") or biz_by_phone.get("business_id")

        # 3) Owners: prefer explicit owner list in profile, else try owner_phone fields
        owners: List[Dict[str, Any]] = []
        try:
            profile = out.get("profile") or {}
            if isinstance(profile.get("owners"), list) and profile.get("owners"):
                owners = profile.get("owners")
            else:
                owner_phone = profile.get("owner_phone") or (profile.get("owner") or {}).get("phone")
                if owner_phone:
                    try:
                        user = await service_helpers.get_user_by_phone(str(owner_phone))
                        if isinstance(user, dict) and user:
                            owners.append(user)
                    except Exception:
                        logger.exception("get_user_by_phone failed")
        except Exception:
            logger.exception("error_resolving_owners")

        out["owners"] = owners

        # 4) Service token for backend-to-backend calls (best-effort)
        if business_id:
            try:
                token = await service_helpers.get_service_token(business_id)
                out["service_token"] = token
            except Exception:
                logger.exception("get_service_token_failed")

        # Attach diagnostics/minor metadata
        out["_meta"]["fetched_by"] = "build_business_blob"
        out["_meta"]["session_id"] = session_id
        out["_meta"]["phone_used"] = phone
        out["_meta"]["business_id_used"] = business_id

        # Use business phone as the Redis cache key when available (string). Fall back to business_id.
        if phone:
            redis_key = f"business:{phone}"
            redis_template = "business:{phone}"
        else:
            redis_key = f"business:{business_id}"
            redis_template = "business:{business_id}"

        out["_meta"]["redis_key"] = redis_key
        out["_meta"]["redis_key_template"] = redis_template

        # Persist & cache the blob (best-effort) using service helpers with the chosen key
        try:
            await service_helpers.persist_and_cache_blob(redis_key, out, session_id=session_id, ttl=out["_meta"].get("ttl", 3600))
        except Exception:
            logger.exception("persist_and_cache_blob failed")

    except Exception:
        logger.exception("build_business_blob_failed")

    # Persist/cache result (best-effort): write to Redis and optionally to bot-session (PSQL)
    try:
        out_copy = dict(out)
        out_copy.setdefault("_meta", {})["cached_at"] = time.time()
        if redis_client and cache_key:
            try:
                await redis_client.set(cache_key, json.dumps(out_copy), ex=86400)
            except Exception:
                logger.exception("failed_writing_business_blob_to_redis")
    except Exception:
        logger.exception("post_build_cache_persist_failed")

    # Persist to bot-session (PSQL) if session_id provided
    try:
        if session_id:
            # store under a session state so bot-session persists object_context in Postgres
            await service_helpers.create_session_state(session_id, "business_blob_cached", object_context={"business": out})
    except Exception:
        logger.exception("failed_persisting_business_blob_to_session")

    return out


async def build_customer_blob(
    *,
    phone: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the `customer` hydrated blob.

    - Lookup user by `phone` (preferred) or `user_id`.
    - If no user found, attempt to register/create a minimal user (marked as placeholder).
    - Persist/cache under `_meta.redis_key` `customer:{phone}` or `customer:{user_id}`.
    """
    out: Dict[str, Any] = {"profile": {}, "preferences": {}, "orders": [], "_meta": {"ttl": 3600}}

    # canonical redis key
    if phone:
        redis_key = f"customer:{phone}"
        redis_template = "customer:{phone}"
    else:
        redis_key = f"customer:{user_id}"
        redis_template = "customer:{user_id}"

    # Check DB for fresh persisted blob first
    try:
        from app.state.repository import AsyncSessionLocal, IceRepository

        try:
            async with AsyncSessionLocal() as db:
                repo = IceRepository(db)
                row = await repo.get_hydrated_blob(redis_key)
                if row:
                    try:
                        updated_ts = row.updated_at.timestamp()
                        age = time.time() - updated_ts
                        if age < out["_meta"].get("ttl", 3600):
                            return row.blob
                    except Exception:
                        logger.exception("error_checking_customer_blob_age")
        except Exception:
            logger.debug("customer hydrated_blob db check unavailable")
    except Exception:
        pass

    # Fetch or create user
    try:
        user = {}
        if phone:
            try:
                user = await service_helpers.get_user_by_phone(phone)
            except Exception:
                logger.exception("get_user_by_phone failed")

        if not user and user_id:
            # No direct helper for get_user_by_id in service_helpers; try phone path only
            user = {}

        # If still no user, ensure one exists (creates placeholder)
        if not user:
            try:
                user = await service_helpers.ensure_user_exists(phone or user_id, display_name="unknown")
            except Exception:
                logger.exception("ensure_user_exists failed")
                user = {}

        out["profile"] = user or {}

        # Attach meta
        out["_meta"]["fetched_by"] = "build_customer_blob"
        out["_meta"]["session_id"] = session_id
        out["_meta"]["phone_used"] = phone
        out["_meta"]["user_id_used"] = user_id
        out["_meta"]["redis_key"] = redis_key
        out["_meta"]["redis_key_template"] = redis_template

        # Persist & cache
        try:
            await service_helpers.persist_and_cache_blob(redis_key, out, session_id=session_id, ttl=out["_meta"].get("ttl", 3600))
        except Exception:
            logger.exception("persist_and_cache_blob failed for customer")

    except Exception:
        logger.exception("build_customer_blob_failed")

    # Final session-state persist (best-effort)
    try:
        out_copy = dict(out)
        out_copy.setdefault("_meta", {})["cached_at"] = time.time()
        # try redis best-effort using aioredis if configured
        try:
            if aioredis and phone and os.environ.get("REDIS_URL"):
                rc = aioredis.from_url(os.environ.get("REDIS_URL"), decode_responses=True)
                await rc.set(redis_key, json.dumps(out_copy), ex=86400)
        except Exception:
            logger.debug("post-build redis set for customer failed")
    except Exception:
        logger.exception("post_build_cache_persist_failed_customer")

    try:
        if session_id:
            await service_helpers.create_session_state(session_id, "customer_blob_cached", object_context={"customer": out})
    except Exception:
        logger.exception("failed_persisting_customer_blob_to_session")

    return out
