"""Hydration workflow for ICE service.

Hydration composes session blob from all adapters:
1. User info from MSME Auth
2. Business profile + policies from MSME
3. Catalog snapshot from Catalog/Inventory
4. Affiliate context (if applicable)

Then persists to Postgres + Redis and emits ice:hydrated event.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import AdapterFactory
from app.cache.redis_client import RedisCache, get_redis_cache
from app.config import Config
from app.state.repository import IceRepository
from app.shared.schema_registry import create_session_blob

logger = logging.getLogger(__name__)
_TEST_DATA_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


class HydrationWorkflow:
    """Orchestration workflow for session hydration."""
    
    def __init__(self, db: AsyncSession, redis: Optional[RedisCache] = None):
        self.db = db
        self.redis = redis or get_redis_cache()
        self.repo = IceRepository(db)
    
    async def hydrate_session(
        self,
        session_id: str,
        phone_number: str,
        business_id: str,
        business_phone: Optional[str] = None,
        platform: Optional[str] = None,
        bot_id: Optional[str] = None,
        bot_type: Optional[str] = None,
        affiliate_code: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Hydrate session by composing context from all adapters.
        
        **Two-number flow (production):**
        - If only phone_number + business_phone provided: lookup both via MSME
        - business_phone → get business ID + profile
        - phone_number → get user ID + profile
        
        Returns:
            Hydrated session blob with all context
        """
        logger.info(f"Starting hydration for session: {session_id}")
        logger.info(f"  from_number (customer): {phone_number}")
        logger.info(f"  to_number (business): {business_phone}")
        
        # **Two-number resolution: Lookup business by phone if not provided**
        if not business_id and business_phone:
            logger.debug(f"Resolving business from phone: {business_phone}")
            business_data = await self._lookup_business_by_phone(business_phone)
            resolved_id = business_data.get("business_id") or business_data.get("id")
            if resolved_id:
                business_id = str(resolved_id)
                logger.info(f"✓ Business resolved: {business_id} ({business_data.get('name')})")
            else:
                logger.warning(f"Could not resolve business from phone: {business_phone}")
                await self.redis.set_negative_cache(f"hydrate:{session_id}", ttl_minutes=5)
                return {}
        
        if not business_id or not business_phone:
            logger.warning(f"No business_id or business_phone available")
            await self.redis.set_negative_cache(f"hydrate:{session_id}", ttl_minutes=5)
            return {}
        
        # Check for single-flight lock (prevent concurrent hydrations)
        lock_acquired = await self.redis.set_lock(f"hydrate:{session_id}", ttl_seconds=60)
        if not lock_acquired:
            logger.warning(f"Hydration lock already held for session: {session_id}")
            return await self._get_cached_session(session_id)
        
        try:
            # Check negative cache (don't retry failed hydrations)
            if await self.redis.get_negative_cache(f"hydrate:{session_id}"):
                logger.info(f"Skipping hydration (negative cache): {session_id}")
                return {}
            
            # **Fetch service token for downstream usage**
            logger.debug(f"Fetching service token for business {business_id}...")
            service_token = await self._fetch_service_token(business_id)
            
            # **Fetch user context from MSME by phone**
            logger.debug(f"Fetching user context from MSME for {phone_number}...")
            user_context = await self._fetch_user_context(phone_number)
            user_id = user_context.get("user_id", "N/A")
            
            # **Fetch business context from MSME by ID**
            logger.debug(f"Fetching business context from MSME for {business_id}...")
            business_context = await self._fetch_business_context(business_id, business_phone)
            
            # **Fetch bot configuration using business phone and token**
            logger.debug(f"Fetching bot config for {business_phone}...")
            bot_config = await self._fetch_bot_config(business_phone, business_id, service_token)
            
            # **Resolve or create bot session**
            logger.debug(f"Resolving/creating bot session for {business_phone}...")
            bot_session = await self._resolve_or_create_bot_session(
                user_phone=business_phone,
                bot_config=bot_config,
                business_id=business_id,
                service_token=service_token,
            )

            # Resolve session state + context with cycle resolution
            cycle_resolution_result = await self._resolve_cycle_state_and_context(
                bot_session=bot_session,
                service_token=service_token,
            )
            current_state = cycle_resolution_result.get("current_state")
            state_context = cycle_resolution_result.get("state_context")
            cycle_resolution = cycle_resolution_result.get("cycle_resolution", {})
            expected_action = self._expected_action_for_state(current_state)
            
            # Fetch catalog from Catalog/Inventory
            logger.debug(f"Fetching catalog snapshot for {business_id}...")
            catalog_context = await self._fetch_catalog_context(business_id)

            # Fetch product snapshots for each product in catalog
            product_snapshots = await self._fetch_product_snapshots(business_id, catalog_context)
            if product_snapshots:
                catalog_context = dict(catalog_context or {})
                catalog_context["product_snapshots"] = product_snapshots
            
            # Fetch affiliate context if affiliate_code provided
            affiliate_context = None
            if affiliate_code:
                logger.debug(f"Fetching affiliate context for code: {affiliate_code}")
                affiliate_context = await self._fetch_affiliate_context(affiliate_code)
            
            # Fetch cart/order draft if in cart or order state
            order_draft_blob = None
            if current_state in ("cart", "order"):
                logger.debug(f"Fetching cart context for session: {session_id}")
                order_draft_blob = await self._fetch_cart_context(session_id, user_id, business_id)
            
            # Create session blob
            resolved_bot_id = bot_id or (bot_config.get("bot_id") if isinstance(bot_config, dict) else None) or "default"
            resolved_bot_type = bot_type or (bot_config.get("bot_type") if isinstance(bot_config, dict) else None) or "MSME"
            blob = create_session_blob(
                session_id=session_id,
                user_id=user_id,
                phone_number=phone_number,
                business_id=business_id,
                user_context=user_context,
                business_context=business_context,
                catalog_context=catalog_context,
                metadata={
                    "bot_id": resolved_bot_id,
                    "bot_type": resolved_bot_type,
                    "platform": platform or "WHATSAPP",
                    "affiliate_code": affiliate_code,
                    "correlation_id": correlation_id,
                    "hydration_timestamp": str(uuid4()),
                    "business_phone": business_phone,
                    "service_token": service_token,
                    "bot_config": bot_config,
                    "bot_session": bot_session,
                    "session_state": current_state,
                    "expected_action": expected_action,
                    "state_context": state_context or {},
                    "affiliate_context": affiliate_context,
                    "order_draft": order_draft_blob,
                    "cycle_resolution": cycle_resolution,  # Include cycle resolution info
                    # Expose authoritative/current cycle id and meta for runtime usage
                    "current_cycle_id": (cycle_resolution.get("cycle_id_to_use") if isinstance(cycle_resolution, dict) else None) or (bot_session.get("current_cycle_id") if isinstance(bot_session, dict) else None),
                    "current_cycle_meta": (cycle_resolution.get("last_cycle_meta") if isinstance(cycle_resolution, dict) else None) or None,
                }
            )

            # Update session_state in blob to reflect resolved state and current context only
            blob["session_state"]["current_node"] = current_state or "chat"
            blob["session_state"]["expected_action"] = expected_action
            blob["session_state"]["state_context"] = state_context or {}
            
            logger.info(f"✓ Session blob created for {session_id}")
            
            # Persist to Postgres (update-or-create)
            try:
                logger.debug("Persisting session to Postgres...")
                existing = await self.repo.get_session(session_id)
                if existing:
                    await self.repo.update_session(session_id, blob)
                else:
                    await self.repo.create_session(session_id, phone_number, business_id, blob)
            except Exception as e:
                logger.warning(f"Could not persist session to Postgres: {e}")
            
            # Cache in Redis
            logger.debug("Caching session in Redis...")
            await self.redis.set_session(session_id, blob, ttl_minutes=30)
            
            # Log audit event (optional)
            try:
                await self.repo.log_event(
                    session_id=session_id,
                    event_type="ice:hydrated",
                    event_payload={
                        "user_context": bool(user_context),
                        "business_context": bool(business_context),
                        "catalog_context": bool(catalog_context),
                        "affiliate_code": affiliate_code,
                    },
                    business_id=business_id,
                    correlation_id=correlation_id,
                )
            except Exception as e:
                logger.warning(f"Could not log audit event: {e}")
            
            # Publish event (optional)
            try:
                await self.redis.publish_event("ice:hydrated", {
                    "session_id": session_id,
                    "business_id": business_id,
                    "phone_number": phone_number,
                    "timestamp": str(uuid4()),
                })
            except Exception as e:
                logger.warning(f"Could not publish event: {e}")
            
            try:
                await self.repo.commit()
            except Exception as e:
                logger.warning(f"Could not commit: {e}")
            
            logger.info(f"✓ Hydration complete for session: {session_id}")
            return blob
        
        except Exception as e:
            logger.error(f"Hydration failed for session {session_id}: {e}", exc_info=True)
            await self.repo.rollback()
            
            # Set negative cache to avoid retry spam
            await self.redis.set_negative_cache(f"hydrate:{session_id}", ttl_minutes=5)
            
            return {}
        
        finally:
            # Release lock
            await self.redis.release_lock(f"hydrate:{session_id}")
    
    async def _fetch_user_context(self, phone_number: str) -> Dict[str, Any]:
        """Fetch user context from MSME backend by phone."""
        try:
            if not phone_number:
                return {
                    "user_id": "placeholder_unknown",
                    "username": "unknown_user",
                    "phone_number": phone_number,
                    "verified": False,
                    "placeholder": True,
                }
            
            logger.info(f"Looking up user by phone: {phone_number}")
            # Call MSME adapter to lookup user by phone (returns {user: {...}, business: {...}})
            msme_adapter = AdapterFactory.get_msme_adapter()
            response = await msme_adapter.get_user_by_phone(phone_number)
            
            if response and response.get("user"):
                user_data = response.get("user", {})
                logger.info(f"✓ User found: {user_data.get('username')}")
                return {
                    "user_id": user_data.get("id"),
                    "username": user_data.get("username", "unknown_user"),
                    "phone_number": phone_number,
                    "verified": True,
                    "placeholder": False,
                    "business_id": user_data.get("business_id"),
                    "email": user_data.get("email"),
                    "role": user_data.get("role"),
                }
            
            # User not found - create placeholder
            logger.warning(f"User not found: {phone_number}, creating placeholder")
            return {
                "user_id": f"placeholder_{phone_number}",
                "username": "unknown_user",
                "phone_number": phone_number,
                "verified": False,
                "placeholder": True,
            }
        except Exception as e:
            logger.warning(f"Failed to fetch user: {e}")
            return {
                "user_id": f"placeholder_{phone_number}",
                "username": "unknown_user",
                "phone_number": phone_number,
                "verified": False,
                "placeholder": True,
            }
    
    async def _fetch_business_context(self, business_id: str, business_phone: Optional[str]) -> Dict[str, Any]:
        """Fetch business context from MSME backend via adapter."""
        try:
            # Call MSME adapter to fetch business profile and policies
            msme_adapter = AdapterFactory.get_msme_adapter()
            
            profile = await msme_adapter.fetch_business_profile(business_id)
            policies = await msme_adapter.fetch_business_policies(business_id)
            
            if profile:
                logger.info(f"✓ Business profile fetched: {business_id}")
                return {
                    "profile": profile,
                    "policies": policies or {},
                }
            
            logger.warning(f"Business profile not found in backend: {business_id}")
            return {
                "profile": {
                    "business_id": business_id,
                    "name": "Unknown Business",
                    "phone_number": business_phone,
                },
                "policies": {},
            }
        except Exception as e:
            logger.warning(f"Failed to fetch business context from backend: {e}")
            return {}

    def _resolve_business_id(self, business_phone: Optional[str]) -> Optional[str]:
        """Resolve business ID from business phone number via MSME backend."""
        # This is handled in hydrate_session via _lookup_business_by_phone
        return None

    async def _lookup_business_by_phone(self, business_phone: str) -> Dict[str, Any]:
        """Lookup business by phone via MSME adapter."""
        try:
            if not business_phone:
                return {}
            
            logger.info(f"Looking up business by phone: {business_phone}")
            msme_adapter = AdapterFactory.get_msme_adapter()
            
            # Call GET /business/phone/{phone} which returns {business: {...}, owner: {...}}
            response = await msme_adapter.get_business_by_phone(business_phone)
            
            if response and response.get("business"):
                # Extract business and owner from response
                business_data = response.get("business", {})
                owner_data = response.get("owner", {})
                logger.info(f"✓ Business found: {business_data.get('name')} (Owner: {owner_data.get('username')})")  
                # Return with both business_id and id for compatibility
                return {
                    "business_id": business_data.get("id"),
                    "id": business_data.get("id"),
                    **business_data
                }
            
            logger.warning(f"Business not found for phone: {business_phone}")
            return {}
        except Exception as e:
            logger.warning(f"Failed to lookup business by phone: {e}", exc_info=True)
            return {}

    async def _fetch_service_token(self, business_id: str) -> Optional[str]:
        """Fetch service JWT token from MSME for downstream service calls."""
        try:
            if not business_id:
                logger.warning("No business_id provided for token fetch")
                return None
            
            logger.info(f"Fetching service token for business: {business_id}")
            msme_adapter = AdapterFactory.get_msme_adapter()
            
            # Call POST /auth/service-token/{business_id}
            import aiohttp
            session = await msme_adapter._get_session()
            async with session.post(
                f"{msme_adapter.base_url}/auth/service-token/{business_id}",
                headers=msme_adapter._build_headers(),
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    access_token = data.get("access_token")
                    logger.info(f"✓ Service token obtained for business {business_id}")
                    return access_token
                else:
                    error = await resp.text()
                    logger.warning(f"Failed to fetch service token: {resp.status} - {error}")
                    return None
        except Exception as e:
            logger.error(f"Exception fetching service token: {e}", exc_info=True)
            return None

    async def _fetch_bot_config(self, business_phone: str, business_id: str, service_token: Optional[str]) -> Dict[str, Any]:
        """Fetch or create bot configuration from bot-session service using business phone."""
        try:
            if not business_phone:
                logger.warning("No business phone provided for bot config fetch")
                return {}
            
            logger.info(f"Fetching bot config for phone: {business_phone}")
            
            # Call bot-session service GET /bot/by-phone/{phone}
            import aiohttp
            bot_session_url = Config.BOT_SESSION_URL
            
            headers = {"accept": "application/json", "Content-Type": "application/json"}
            if service_token:
                headers["Authorization"] = f"Bearer {service_token}"
            
            async with aiohttp.ClientSession() as session:
                # Try to fetch existing bot
                async with session.get(
                    f"{bot_session_url}/bot/by-phone/{business_phone}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        bot_data = await resp.json()
                        logger.info(f"✓ Bot config fetched for {business_phone}: {bot_data.get('bot_id')}")
                        return bot_data
                    elif resp.status == 404:
                        logger.info(f"Bot not found for {business_phone}, creating new bot...")
                        
                        # Create new bot
                        bot_payload = {
                            "phone_number": business_phone,
                            "type": "custom",  # Custom bot type
                            "business_id": business_id
                        }
                        
                        async with session.post(
                            f"{bot_session_url}/bot/create",
                            headers=headers,
                            json=bot_payload,
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as create_resp:
                            if create_resp.status == 200:
                                new_bot = await create_resp.json()
                                logger.info(f"✓ Bot created for {business_phone}: {new_bot.get('bot_id')}")
                                # Fetch full bot details
                                async with session.get(
                                    f"{bot_session_url}/bot/by-phone/{business_phone}",
                                    headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=5)
                                ) as fetch_resp:
                                    if fetch_resp.status == 200:
                                        return await fetch_resp.json()
                                return new_bot
                            elif create_resp.status == 409:
                                # Bot already exists (race condition), try fetching again
                                logger.info(f"Bot already exists (409), fetching again...")
                                async with session.get(
                                    f"{bot_session_url}/bot/by-phone/{business_phone}",
                                    headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=5)
                                ) as retry_resp:
                                    if retry_resp.status == 200:
                                        return await retry_resp.json()
                                return {}
                            else:
                                error = await create_resp.text()
                                logger.warning(f"Failed to create bot: {create_resp.status} - {error}")
                                return {}
                    else:
                        error = await resp.text()
                        logger.warning(f"Failed to fetch bot config: {resp.status} - {error}")
                        return {}
        except Exception as e:
            logger.error(f"Exception fetching/creating bot config: {e}", exc_info=True)
            return {}

    async def _resolve_or_create_bot_session(
        self,
        user_phone: str,
        bot_config: Dict[str, Any],
        business_id: str,
        service_token: Optional[str],
    ) -> Dict[str, Any]:
        """Resolve bot session or create one if not found."""
        try:
            if not user_phone:
                logger.warning("No user_phone provided for session resolve")
                return {}

            bot_id = bot_config.get("bot_id") if bot_config else None
            bot_type = bot_config.get("bot_type") if bot_config else "custom"
            if not bot_id:
                logger.warning("No bot_id available for session resolve")
                return {}

            import aiohttp
            bot_session_url = Config.BOT_SESSION_URL

            headers = {"accept": "application/json", "Content-Type": "application/json"}
            if service_token:
                headers["Authorization"] = f"Bearer {service_token}"

            async with aiohttp.ClientSession() as session:
                # Try to resolve existing session
                resolve_url = (
                    f"{bot_session_url}/session/resolve"
                    f"?user_phone={user_phone}&bot_id={bot_id}&platform=WHATSAPP"
                )
                async with session.get(resolve_url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info(f"✓ Session resolved for {user_phone}: {data.get('id') or data.get('session_id')}")
                        return data
                    elif resp.status not in (404, 204):
                        error = await resp.text()
                        logger.warning(f"Failed to resolve session: {resp.status} - {error}")

                # Create session if not found
                create_payload = {
                    "user_phone": user_phone,
                    "bot_id": bot_id,
                    "bot_phone": user_phone,
                    "bot_type": bot_type or "custom",
                    "business_id": business_id,
                    "platform": "WHATSAPP",
                    "affiliate_code": None,
                    "affiliate_id": None,
                    "affiliate_metadata": {},
                }
                async with session.post(
                    f"{bot_session_url}/session/create",
                    headers=headers,
                    json=create_payload,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as create_resp:
                    if create_resp.status == 200:
                        created = await create_resp.json()
                        logger.info(f"✓ Session created for {user_phone}: {created.get('id') or created.get('session_id')}")
                        return created
                    else:
                        error = await create_resp.text()
                        logger.warning(f"Failed to create session: {create_resp.status} - {error}")
                        return {}
        except Exception as e:
            logger.error(f"Exception resolving/creating session: {e}", exc_info=True)
            return {}

    async def _resolve_cycle_state_and_context(
        self,
        bot_session: Dict[str, Any],
        service_token: Optional[str],
    ) -> Dict[str, Any]:
        """Resolve last cycle state and context for session continuity.
        
        Returns:
            {
                "current_state": str,
                "state_context": dict,
                "cycle_resolution": {
                    "last_cycle_completed": bool,
                    "last_cycle_context": dict or None,
                    "should_start_new_chat_cycle": bool,
                    "cycle_id_to_use": str or None
                }
            }
        """
        try:
            session_id = bot_session.get("session_id") or bot_session.get("id") if bot_session else None
            if not session_id:
                return {"current_state": None, "state_context": {}, "cycle_resolution": {"last_cycle_completed": False, "last_cycle_context": None, "should_start_new_chat_cycle": False, "cycle_id_to_use": None}}

            import aiohttp
            bot_session_url = Config.BOT_SESSION_URL

            headers = {"accept": "application/json"}
            if service_token:
                headers["Authorization"] = f"Bearer {service_token}"

            # Get the last cycle (most recent by started_at)
            async with aiohttp.ClientSession() as session:
                resp = await session.get(
                    f"{bot_session_url}/admin/session/{session_id}/full",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=5)
                )
                if resp.status == 200:
                    full_data = await resp.json()
                    cycles = full_data.get("cycles", [])

                    if not cycles:
                        # No cycles yet, start fresh
                        return {
                            "current_state": "chat",
                            "state_context": {},
                            "cycle_resolution": {
                                "last_cycle_completed": False,
                                "last_cycle_context": None,
                                "should_start_new_chat_cycle": True,
                                "cycle_id_to_use": None
                            }
                        }

                    # Get the most recent cycle
                    last_cycle = cycles[-1]
                    if not last_cycle:
                        return {
                            "current_state": "chat",
                            "state_context": {},
                            "cycle_resolution": {
                                "last_cycle_completed": False,
                                "last_cycle_context": None,
                                "should_start_new_chat_cycle": True,
                                "cycle_id_to_use": None
                            }
                        }

                    last_cycle_completed = last_cycle.get("completed_at") is not None
                    last_cycle_state = last_cycle.get("cycle_state")
                    last_cycle_meta = last_cycle.get("meta") or {}
                    last_cycle_context = last_cycle_meta.get("context") or {}

                    if last_cycle_completed:
                        # Last cycle is closed, fetch its context and start new chat cycle
                        return {
                            "current_state": "chat",
                            "state_context": last_cycle_context,
                            "cycle_resolution": {
                                "last_cycle_completed": True,
                                "last_cycle_context": last_cycle_context,
                                "should_start_new_chat_cycle": True,
                                "cycle_id_to_use": None
                            }
                        }
                    else:
                        # Last cycle is still open, reuse it
                        # Get current session state context
                        ctx_resp = await session.get(
                            f"{bot_session_url}/session/{session_id}/context",
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=5)
                        )
                        current_state = last_cycle_state
                        state_context = {}
                        if ctx_resp.status == 200:
                            ctx_data = await ctx_resp.json()
                            current_state = ctx_data.get("current_state") or last_cycle_state
                            object_context = ctx_data.get("object_context") or {}
                            state_context = object_context.get(current_state, {}) if current_state else {}

                        return {
                            "current_state": current_state,
                            "state_context": state_context,
                            "cycle_resolution": {
                                "last_cycle_completed": False,
                                "last_cycle_context": None,
                                "should_start_new_chat_cycle": False,
                                "cycle_id_to_use": last_cycle.get("id"),
                                "last_cycle_meta": last_cycle_meta,
                            }
                        }
                else:
                    error = await resp.text()
                    logger.warning(f"Failed to fetch full session data: {resp.status} - {error}")
                    # Fallback to current session context only
                    return await self._fetch_session_state_context(bot_session, service_token)
        except Exception as e:
            logger.error(f"Exception resolving cycle state: {e}", exc_info=True)
            # Fallback to current session context only
            return await self._fetch_session_state_context(bot_session, service_token)

    async def _fetch_session_state_context(self, bot_session: Dict[str, Any], service_token: Optional[str]) -> Dict[str, Any]:
        """Compatibility fallback: fetch current session state/context from bot-session service.

        Returns normalized structure matching _resolve_cycle_state_and_context output.
        """
        try:
            session_id = bot_session.get("session_id") or bot_session.get("id") if bot_session else None
            if not session_id:
                return {"current_state": None, "state_context": {}, "cycle_resolution": {"last_cycle_completed": False, "last_cycle_context": None, "should_start_new_chat_cycle": False, "cycle_id_to_use": None, "last_cycle_meta": None}}

            import aiohttp
            bot_session_url = Config.BOT_SESSION_URL

            headers = {"accept": "application/json"}
            if service_token:
                headers["Authorization"] = f"Bearer {service_token}"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{bot_session_url}/session/{session_id}/context",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        current_state = data.get("current_state")
                        object_context = data.get("object_context") or {}
                        state_context = object_context.get(current_state, {}) if current_state else {}
                        return {
                            "current_state": current_state or "chat",
                            "state_context": state_context,
                            "cycle_resolution": {
                                "last_cycle_completed": False,
                                "last_cycle_context": None,
                                "should_start_new_chat_cycle": True,
                                "cycle_id_to_use": None,
                                "last_cycle_meta": None,
                            }
                        }
                    else:
                        # No context available; default to chat
                        return {
                            "current_state": "chat",
                            "state_context": {},
                            "cycle_resolution": {
                                "last_cycle_completed": False,
                                "last_cycle_context": None,
                                "should_start_new_chat_cycle": True,
                                "cycle_id_to_use": None,
                                "last_cycle_meta": None,
                            }
                        }
        except Exception as e:
            logger.warning(f"Fallback fetch session context failed: {e}")
            return {"current_state": "chat", "state_context": {}, "cycle_resolution": {"last_cycle_completed": False, "last_cycle_context": None, "should_start_new_chat_cycle": True, "cycle_id_to_use": None, "last_cycle_meta": None}}

    def _expected_action_for_state(self, state: Optional[str]) -> Dict[str, Any]:
        """Return expected action for a given session state."""
        state_key = (state or "chat").lower()
        expected_actions = {
            "chat": {
                "action": "show_menu",
                "required_context_keys": [],
            },
            "cart": {
                "action": "review_cart",
                "required_context_keys": ["selected_items"],
            },
            "order": {
                "action": "collect_order_details",
                "required_context_keys": ["cart_summary"],
            },
            "payment": {
                "action": "await_payment",
                "required_context_keys": ["fulfillment", "contact", "order_total"],
            },
            "delivery": {
                "action": "await_delivery_confirmation",
                "required_context_keys": ["payment_status", "transaction_id"],
            },
            "closed": {
                "action": "session_closed",
                "required_context_keys": ["delivery_status", "delivery_code"],
            },
        }
        return expected_actions.get(state_key, expected_actions["chat"])

    async def _fetch_affiliate_context(self, affiliate_code: str) -> Optional[Dict[str, Any]]:
        """Fetch affiliate context from affiliate-engine."""
        try:
            affiliate_adapter = AdapterFactory.get_affiliate_adapter()
            result = await affiliate_adapter.hydrate_affiliate_context({
                "affiliate_code": affiliate_code
            })
            context = result.get("affiliate_context")
            if context:
                logger.info(f"✓ Affiliate context fetched for code: {affiliate_code}")
                return context
            return None
        except Exception as e:
            logger.warning(f"Failed to fetch affiliate context: {e}")
            return None

    async def _fetch_cart_context(
        self,
        session_id: str,
        user_id: str,
        business_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch active cart/order draft from cart service."""
        try:
            cart_adapter = AdapterFactory.get_cart_order_adapter()
            
            # Try to get active draft by session_id
            import aiohttp
            from app.config import Config
            
            cart_url = Config.CART_SERVICE_URL
            if not cart_url:
                logger.warning("Cart service URL not configured")
                return None
            
            async with aiohttp.ClientSession() as session:
                # Get active cart by session or user
                async with session.get(
                    f"{cart_url}/cart/active",
                    params={"session_id": session_id, "user_id": user_id},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        cart_data = await resp.json()
                        logger.info(f"✓ Cart context fetched for session: {session_id}")
                        return cart_data
                    elif resp.status == 404:
                        logger.debug(f"No active cart found for session: {session_id}")
                        return None
                    else:
                        logger.warning(f"Cart fetch failed: {resp.status}")
                        return None
        except Exception as e:
            logger.warning(f"Failed to fetch cart context: {e}")
            return None

    def _load_test_data_ids(self) -> Dict[str, Dict[str, Any]]:
        """Load test_data_ids.txt into lookup maps (cached)."""
        global _TEST_DATA_CACHE
        if _TEST_DATA_CACHE is not None:
            return _TEST_DATA_CACHE

        base_dir = Path(__file__).resolve().parents[2]
        path = base_dir / "test_data_ids.txt"
        if not path.exists():
            _TEST_DATA_CACHE = {}
            return _TEST_DATA_CACHE

        lines = path.read_text(encoding="utf-8").splitlines()
        users_by_phone: Dict[str, Dict[str, Any]] = {}
        businesses_by_id: Dict[str, Dict[str, Any]] = {}
        owners_by_business_id: Dict[str, Dict[str, Any]] = {}
        business_by_phone: Dict[str, str] = {}

        section = None
        for raw_line in lines:
            line = raw_line.strip()
            if line.startswith("===") and line.endswith("==="):
                section = line.strip("=").strip()
                continue

            if not line or not line.startswith("ID:"):
                continue

            if section == "MSME BUSINESSES":
                match = re.match(r"ID:\s*([^,]+),\s*Name:\s*([^,]+),\s*Code:\s*(.+)", line)
                if match:
                    business_id, name, code = [part.strip() for part in match.groups()]
                    businesses_by_id[business_id] = {
                        "name": name,
                        "code": code,
                    }
                continue

            if section == "USERS":
                match = re.match(
                    r"ID:\s*([^,]+),\s*Username:\s*([^,]+),\s*Phone:\s*([^,]+),\s*Business:\s*(.+)",
                    line,
                )
                if match:
                    user_id, username, phone, business_id = [part.strip() for part in match.groups()]
                    business_id = None if business_id in {"None", "null", ""} else business_id
                    users_by_phone[phone] = {
                        "user_id": user_id,
                        "username": username,
                        "business_id": business_id,
                    }
                    if business_id:
                        owners_by_business_id.setdefault(
                            business_id,
                            {
                                "user_id": user_id,
                                "username": username,
                                "phone_number": phone,
                            },
                        )
                        business_by_phone.setdefault(phone, business_id)

        _TEST_DATA_CACHE = {
            "users_by_phone": users_by_phone,
            "businesses_by_id": businesses_by_id,
            "owners_by_business_id": owners_by_business_id,
            "business_by_phone": business_by_phone,
        }
        return _TEST_DATA_CACHE
    
    async def _fetch_catalog_context(self, business_id: str) -> Dict[str, Any]:
        """Fetch catalog context from Catalog/Inventory adapter."""
        try:
            # Check Redis cache first
            cached = await self.redis.get_catalog(business_id)
            if cached:
                logger.debug(f"Using cached catalog for business: {business_id}")
                return cached
            
            # Fetch from adapter
            catalog_adapter = AdapterFactory.get_catalog_adapter()
            catalog = await catalog_adapter.fetch_catalog_index(business_id)
            
            # Cache in Redis
            await self.redis.set_catalog(business_id, catalog, ttl_minutes=5)
            
            # Optionally persist to DB (ignore if tables not migrated yet)
            try:
                await self.repo.save_catalog_snapshot(business_id, catalog)
            except Exception as e:
                logger.warning(f"Could not persist catalog snapshot: {e}")
                try:
                    await self.db.rollback()
                except Exception:
                    pass
            
            return catalog
        except Exception as e:
            logger.warning(f"Failed to fetch catalog context: {e}")
            return {}
    
    async def _get_cached_session(self, session_id: str) -> Dict[str, Any]:
        """Get cached session from Redis."""
        cached = await self.redis.get_session(session_id)
        if cached:
            return cached
        
        # Try to get from Postgres
        session = await self.repo.get_session(session_id)
        if session:
            return session.blob
        
        return {}

    async def _fetch_product_snapshots(self, business_id: str, catalog_context: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch per-product snapshots (product + variants + inventory)."""
        try:
            products = (catalog_context or {}).get("products", [])
            if not products:
                return {}

            snapshots: Dict[str, Any] = {}
            catalog_adapter = AdapterFactory.get_catalog_adapter()

            for product in products:
                product_id = product.get("id") or product.get("product_id")
                if not product_id:
                    continue

                # Redis cache check
                cached = await self.redis.get_product_snapshot(product_id)
                if cached:
                    snapshots[str(product_id)] = cached
                    continue

                snapshot = await catalog_adapter.fetch_product_snapshot(business_id, str(product_id))
                snapshots[str(product_id)] = snapshot

                # Cache in Redis
                await self.redis.set_product_snapshot(str(product_id), snapshot, ttl_minutes=10)

                # Persist to Postgres (ignore if tables not migrated yet)
                try:
                    await self.repo.save_product_snapshot(business_id, str(product_id), snapshot)
                except Exception as e:
                    logger.warning(f"Could not persist product snapshot: {e}")
                    try:
                        await self.db.rollback()
                    except Exception:
                        pass

            return snapshots
        except Exception as e:
            logger.warning(f"Failed to fetch product snapshots: {e}")
            return {}
