"""MSME adapter for business profile and policy hydration."""

import logging
from typing import Any, Dict, Optional
from uuid import uuid4

import aiohttp

from app.config import Config
from .base import MsmeAdapter

logger = logging.getLogger(__name__)


class MsmeEngineAdapter(MsmeAdapter):
    """HTTP-backed MSME adapter for business profile and entitlements."""

    def __init__(self, base_url: str = Config.MSME_ENGINE_URL):
        self.base_url = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def health_check(self) -> bool:
        """Check if MSME service is reachable."""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/health", timeout=aiohttp.ClientTimeout(total=3)) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"MSME health check failed: {e}")
            return False

    async def fetch_business_profile(self, business_id: str) -> Dict[str, Any]:
        """Fetch business profile including name, owner, location, tags."""
        try:
            session = await self._get_session()
            headers = self._build_headers()
            
            async with session.get(
                f"{self.base_url}/business/{business_id}",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    profile = await resp.json()
                    logger.info(f"Fetched business profile for {business_id}")
                    return profile
                elif resp.status == 404:
                    logger.warning(f"Business {business_id} not found")
                    return {}
                else:
                    error = await resp.text()
                    logger.error(f"MSME fetch profile failed: {resp.status} - {error}")
                    return {}
        except Exception as e:
            logger.error(f"Exception fetching business profile: {e}")
            return {}

    async def fetch_business_policies(self, business_id: str) -> Dict[str, Any]:
        """Fetch business policies and entitlements (subscription plan, features)."""
        try:
            session = await self._get_session()
            headers = self._build_headers()
            
            async with session.get(
                f"{self.base_url}/business/{business_id}/entitlements",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    entitlements = await resp.json()
                    logger.info(f"Fetched business policies for {business_id}")
                    return entitlements
                elif resp.status == 404:
                    logger.warning(f"Business {business_id} policies not found")
                    return {}
                else:
                    error = await resp.text()
                    logger.error(f"MSME fetch policies failed: {resp.status} - {error}")
                    return {}
        except Exception as e:
            logger.error(f"Exception fetching business policies: {e}")
            return {}

    async def get_business_by_phone(self, phone_number: str) -> Dict[str, Any]:
        """Lookup business by phone number."""
        try:
            session = await self._get_session()
            headers = self._build_headers()
            
            async with session.get(
                f"{self.base_url}/business/phone/{phone_number}",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    business = await resp.json()
                    logger.info(f"Fetched business by phone: {phone_number}")
                    return business
                elif resp.status == 404:
                    logger.warning(f"Business not found for phone: {phone_number}")
                    return {}
                else:
                    error = await resp.text()
                    logger.error(f"MSME lookup business failed: {resp.status} - {error}")
                    return {}
        except Exception as e:
            logger.error(f"Exception looking up business by phone: {e}")
            return {}

    async def get_user_by_phone(self, phone_number: str) -> Dict[str, Any]:
        """Lookup user by phone number. Returns {user: {...}, business: {...}} if user is linked to a business."""
        try:
            session = await self._get_session()
            headers = self._build_headers()
            
            async with session.get(
                f"{self.base_url}/auth/phone/{phone_number}",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"Fetched user by phone: {phone_number}")
                    return data
                elif resp.status == 404:
                    logger.warning(f"User not found for phone: {phone_number}")
                    return {}
                else:
                    error = await resp.text()
                    logger.error(f"MSME lookup user failed: {resp.status} - {error}")
                    return {}
        except Exception as e:
            logger.error(f"Exception looking up user by phone: {e}")
            return {}

    @staticmethod
    def _build_headers() -> Dict[str, str]:
        """Build auth headers for MSME service."""
        return {
            "Authorization": "Bearer dummy-token",
            "X-Correlation-Id": str(uuid4()),
            "X-Idempotency-Key": str(uuid4()),
        }

    async def cleanup(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()

    async def fetch_business_delivery_locations(self, business_id: str) -> list[dict]:
        """Fetch delivery locations mapping or list from MSME and normalize to list of dicts.

        Returns empty list on error or when no locations configured.
        """
        try:
            session = await self._get_session()
            headers = self._build_headers()
            async with session.get(
                f"{self.base_url}/businesses/{business_id}/delivery-locations",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # If MSME returns mapping {name: meta}, convert to list
                    if isinstance(data, dict):
                        out: list[dict] = []
                        for name, meta in data.items():
                            if not isinstance(meta, dict):
                                continue
                            loc = dict(meta)
                            if "name" not in loc and "label" not in loc:
                                loc.setdefault("name", name)
                            out.append(loc)
                        return out
                    if isinstance(data, list):
                        return [d for d in data if isinstance(d, dict)]
                    return []
                elif resp.status == 404:
                    return []
                else:
                    error = await resp.text()
                    logger.error(f"MSME fetch delivery locations failed: {resp.status} - {error}")
                    return []
        except Exception as e:
            logger.error(f"Exception fetching delivery locations: {e}")
            return []
