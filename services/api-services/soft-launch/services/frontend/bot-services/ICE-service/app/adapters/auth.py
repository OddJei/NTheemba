"""
Authentication Adapter

Handles user authentication by calling MSME Engine service.
This adapter verifies user identity and retrieves user information
needed for session context (role, business_id, etc.).
"""
import os
from typing import Optional, Dict, Any
import httpx
import logging
from app.config import Config

logger = logging.getLogger(__name__)


class AuthenticationAdapter:
    """
    Adapter for MSME Engine authentication service.
    
    Responsibilities:
    - User authentication (phone/OTP)
    - User info retrieval (role, business_id, etc.)
    - Session context enrichment
    """
    
    def __init__(
        self, 
        base_url: Optional[str] = None, 
        timeout: Optional[float] = None
    ):
        # Get base URL from parameter or environment
        if base_url is None:
            base_url = Config.MSME_ENGINE_URL
        
        # Get timeout from parameter or environment
        if timeout is None:
            timeout = Config.MSME_ENGINE_TIMEOUT
        
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        
        logger.info(f"AuthenticationAdapter initialized with base_url={self.base_url}, timeout={self.timeout}s")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def health_check(self) -> bool:
        """
        Check if MSME Engine service is reachable.
        
        Endpoint: GET /health
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/health")
            if response.status_code == 200:
                data = response.json()
                return data.get("status") == "ok"
            return False
        except Exception as e:
            logger.error(f"MSME Engine health check failed: {e}")
            return False
    
    async def verify_user(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """
        Verify user and retrieve user information.
        
        Args:
            phone_number: User's phone number
        
        Returns:
            User info dict or None if not found:
            {
                "phone": str,
                "role": str,  # msme/customer/staff/admin
                "business_id": str (optional, if role=msme),
                "user_id": str,
                "status": str
            }
        
        Endpoint: GET /auth/phone/{phone_number}
        
        This endpoint is used internally by bot-session to determine
        session_mode (registered vs public), but we expose it here
        for ICE service to enrich session context.
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/auth/phone/{phone_number}")
            
            if response.status_code == 404:
                logger.info(f"User {phone_number} not found")
                return None
            
            if response.status_code == 200:
                user_info = response.json()
                logger.info(f"User {phone_number} verified, role: {user_info.get('role')}")
                return user_info
            
            logger.error(f"Failed to verify user {phone_number}: {response.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"Error verifying user {phone_number}: {e}")
            return None
    
    async def get_business_profile(self, business_id: str) -> Optional[Dict[str, Any]]:
        """
        Get business profile information.
        
        Args:
            business_id: Business identifier
        
        Returns:
            Business profile dict or None if not found:
            {
                "business_id": str,
                "business_name": str,
                "owner_phone": str,
                "status": str,
                "policies": dict,
                "features": dict
            }
        
        Endpoint: GET /businesses/{business_id}
        
        This allows ICE service to fetch business-specific settings
        and policies needed for order processing.
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/businesses/{business_id}")
            
            if response.status_code == 404:
                logger.warning(f"Business {business_id} not found")
                return None
            
            if response.status_code == 200:
                business_info = response.json()
                logger.info(f"Retrieved business profile for {business_id}")
                return business_info
            
            logger.error(f"Failed to get business profile {business_id}: {response.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting business profile {business_id}: {e}")
            return None
