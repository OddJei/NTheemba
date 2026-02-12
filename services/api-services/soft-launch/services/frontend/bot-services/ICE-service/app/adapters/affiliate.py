"""Affiliate adapter for attribution logging and context hydration."""

import logging
from typing import Any, Dict, Optional
from uuid import uuid4

import aiohttp

from app.config import Config
from .base import AffiliateAdapter

logger = logging.getLogger(__name__)


class AffiliateEngineAdapter(AffiliateAdapter):
    """HTTP-backed Affiliate adapter for attribution and context hydration."""

    def __init__(self, base_url: str = Config.AFFILIATE_ENGINE_URL):
        self.base_url = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def health_check(self) -> bool:
        """Check if Affiliate service is reachable."""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/health", timeout=aiohttp.ClientTimeout(total=3)) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"Affiliate health check failed: {e}")
            return False

    async def hydrate_affiliate_context(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Hydrate affiliate context for a session.
        
        Payload expected to contain one of:
        - affiliate_id (str): Affiliate identifier (preferred)
        - affiliate_code (str): Legacy affiliate identifier (deprecated)
        - session_id (str): User session ID
        - optional: token (str): Affiliate token for resolution
        """
        try:
            # Prefer `affiliate_id`, fall back to legacy `affiliate_code` for compatibility
            affiliate_id = payload.get("affiliate_id") or payload.get("affiliate_code")
            if not affiliate_id:
                logger.info("No affiliate id/code provided, skipping context hydration")
                return {"affiliate_context": None}

            session = await self._get_session()
            headers = self._build_headers()

            # Resolve affiliate by id (or legacy code value)
            async with session.get(
                f"{self.base_url}/a/{affiliate_id}/resolve",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    context = await resp.json()
                    logger.info(f"Hydrated affiliate context for id/code: {affiliate_id}")
                    return {
                        "affiliate_context": context,
                        "affiliate_id": affiliate_id,
                    }
                elif resp.status == 404:
                    logger.warning(f"Affiliate id/code {affiliate_id} not found")
                    return {"affiliate_context": None, "affiliate_id": affiliate_id}
                else:
                    error = await resp.text()
                    logger.error(f"Affiliate hydration failed: {resp.status} - {error}")
                    return {"affiliate_context": None, "error": error}
        except Exception as e:
            logger.error(f"Exception hydrating affiliate context: {e}")
            return {"affiliate_context": None, "error": str(e)}

    async def emit_attribution_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Emit attribution event for order conversion.
        
        Payload expected to contain:
        - order_id (str): Order ID
        - business_id (str): Business ID (MSME context)
        - affiliate_id (str): Affiliate ID
        - event_id (str): Unique event ID (for idempotency)
        - amount_minor (int): Order amount in minor units
        - optional: order_details (dict): Additional order metadata
        """
        try:
            event_id = payload.get("event_id", str(uuid4()))
            order_id = payload.get("order_id")
            affiliate_id = payload.get("affiliate_id")
            business_id = payload.get("business_id")
            
            if not order_id or not affiliate_id or not business_id:
                logger.warning(f"Missing order_id, affiliate_id, or business_id for attribution event")
                return {"success": False, "error": "Missing required fields"}
            
            session = await self._get_session()
            headers = self._build_headers()
            headers["X-Idempotency-Key"] = event_id
            
            # Post attribution event
            attribution_payload = {
                "event_id": event_id,
                "order_id": order_id,
                "business_id": business_id,
                "affiliate_id": affiliate_id,
                "amount_minor": payload.get("amount_minor", 0),
                "metadata": payload.get("order_details", {}),
            }
            
            async with session.post(
                f"{self.base_url}/attribute/order",
                json=attribution_payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status in (200, 201):
                    result = await resp.json()
                    logger.info(f"Emitted attribution event for order {order_id}, affiliate {affiliate_id}")
                    return {"success": True, "attribution": result}
                else:
                    error = await resp.text()
                    logger.error(f"Attribution emission failed: {resp.status} - {error}")
                    return {"success": False, "error": error}
        except Exception as e:
            logger.error(f"Exception emitting attribution event: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def _build_headers() -> Dict[str, str]:
        """Build headers for Affiliate service."""
        return {
            "Authorization": "Bearer dummy-token",
            "X-Correlation-Id": str(uuid4()),
            "Content-Type": "application/json",
        }

    async def cleanup(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
