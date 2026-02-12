"""
User-Bot Session Adapter

Handles user-bot conversation session lifecycle, context management,
and session state transitions via the bot-session service.

ENDPOINT MAPPING (from services/bot-session/src/app/main.py):
-------------------------------------------------------------
Session Lifecycle:
- POST /session/create                          → Create or reactivate session
    Payload: {user_phone, bot_id?, bot_phone?, bot_type?, business_id?, platform, affiliate_id?, affiliate_metadata?}
  Returns: {session_id, user_phone, bot_id, platform, session_mode, status, state, created_at, ...}
  
- GET /session/{session_id}                     → Get session metadata
  Returns: {id, user_phone, bot_id, platform, session_mode, status, last_event_id}
  
- POST /session/{session_id}/close              → Close session
  Returns: {session_id, status, closed_at}
  
- GET /session/resolve                          → Resolve session by filters
  Query params: user_phone?, bot_id?, platform?
  
- GET /session/by-phone-platform/{user_phone}/{platform} → List sessions
  Returns: [{id, bot_id, status, session_mode}, ...]

Session State Management:
- Session.state field: chat → cart → order → payment → delivery → closed
- Session.object_context (JSONB): Arbitrary context storage
- Session.session_mode: public/registered/customer/staff (determined by MSME auth lookup)
- SessionStateCycle: Tracks affiliate attribution per state transition

NOTE: No dedicated PATCH /session/{id}/context endpoint exists.
Context updates require direct DB access or new endpoint implementation.
"""
import os
from typing import Optional
import httpx
import logging
from .base import UserBotSessionAdapter

logger = logging.getLogger(__name__)


class UserBotConversationAdapter(UserBotSessionAdapter):
    """
    Adapter for user-bot conversation session management.
    
    Responsibilities:
    - Session lifecycle (create, update, close)
    - Conversation context management
    - Session state tracking
    - Multi-session handling per user
    
    Configuration:
    - BOT_SESSION_URL: URL of bot-session service (default: http://bot-session:8540)
    - ICE_BOT_SESSION_TIMEOUT: HTTP timeout in seconds (default: 5.0)
    """
    
    def __init__(
        self, 
        base_url: Optional[str] = None, 
        timeout: Optional[float] = None
    ):
        # Get base URL from parameter or environment
        if base_url is None:
            base_url = os.getenv("BOT_SESSION_URL", "http://bot-session:8540")
        
        # Get timeout from parameter or environment
        if timeout is None:
            timeout = float(os.getenv("ICE_BOT_SESSION_TIMEOUT", "5.0"))
        
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        
        logger.info(f"UserBotConversationAdapter initialized with base_url={self.base_url}, timeout={self.timeout}s")
    
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
        """Check if bot-session service is reachable."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/health")
            if response.status_code == 200:
                data = response.json()
                return data.get("status") == "ok"
            return False
        except Exception as e:
            logger.error(f"Bot-session health check failed: {e}")
            return False
    
    async def create_session(
        self, 
        phone_number: str, 
        business_id: str, 
        metadata: dict
    ) -> dict:
        """
        Create a new user-bot conversation session.
        
        Args:
            phone_number: User's phone number (session owner)
            business_id: Business context for the session
            metadata: Additional session metadata (entry point, referrer, etc.)
        
        Returns:
            Session object with session_id, created_at, state
        
        Endpoint: POST /session/create
        Payload: {
            "user_phone": str (required),
            "bot_id": str (optional - if known),
            "bot_phone": str (optional - lookup bot by phone),
            "bot_type": str (optional),
            "business_id": str (optional),
            "platform": str (required - e.g., "whatsapp"),
            "affiliate_id": str (optional),
            "affiliate_metadata": dict (optional)
        }
        
        Returns: {
            "session_id": str,
            "user_phone": str,
            "bot_id": str,
            "business_id": str,
            "platform": str,
            "session_mode": str,  # public/registered/customer/staff
            "status": str,  # active/inactive/closed
            "state": str,  # chat/cart/order/payment/delivery/closed
            "created_at": str,
            "reactivated": bool  # true if existing session was reactivated
        }
        
        Notes:
        - If session exists (same user_phone + bot_id + platform), it's reactivated
        - session_mode auto-determined via MSME auth lookup (registered vs public)
        - New sessions start in 'chat' state
        - Affiliate attribution recorded in SessionStateCycle if provided
        """
        try:
            client = await self._get_client()
            
            # Build payload from args + metadata
            payload = {
                "user_phone": phone_number,
                "platform": metadata.get("platform", "whatsapp"),
                "business_id": business_id,
            }
            
            # Add optional fields from metadata
            if "bot_id" in metadata:
                payload["bot_id"] = metadata["bot_id"]
            if "bot_phone" in metadata:
                payload["bot_phone"] = metadata["bot_phone"]
            if "bot_type" in metadata:
                payload["bot_type"] = metadata["bot_type"]
            if "affiliate_id" in metadata:
                payload["affiliate_id"] = metadata["affiliate_id"]
            if "affiliate_metadata" in metadata:
                payload["affiliate_metadata"] = metadata["affiliate_metadata"]
            
            response = await client.post(
                f"{self.base_url}/session/create",
                json=payload
            )
            
            if response.status_code in (200, 201):
                return response.json()
            
            logger.error(
                f"Failed to create session for {phone_number}: "
                f"{response.status_code} {response.text}"
            )
            raise Exception(f"Session creation failed: {response.status_code}")
            
        except Exception as e:
            logger.error(f"Error creating session for {phone_number}: {e}")
            raise
    
    async def get_session_state(self, session_id: str) -> Optional[dict]:
        """
        Get current session state including conversation context.
        
        Args:
            session_id: Unique session identifier
        
        Returns:
            Session state with:
            - session_id, phone_number, business_id
            - conversation_context (last intent, cart state, selections)
            - session_status (active, idle, closed)
            - timestamps (created_at, updated_at, expires_at)
        
        Backend endpoint: GET /session/{session_id}
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/session/{session_id}")
            
            if response.status_code == 404:
                return None
            
            if response.status_code == 200:
                return response.json()
            
            logger.error(f"Failed to get session state {session_id}: {response.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting session state {session_id}: {e}")
            return None
    
    async def update_session_context(
        self, 
        session_id: str, 
        context_updates: dict
    ) -> bool:
        """
        Update session context (cart, selections, conversation state).
        
        Args:
            session_id: Session to update
            context_updates: Partial context updates to merge
                - cart_items: Updated cart state
                - last_intent: Most recent user intent
                - selections: User selections/preferences
                - custom_data: Business-specific context
        
        Returns:
            True if update succeeded
        
        IMPLEMENTATION NOTE:
        The bot-session service does NOT have a dedicated endpoint for
        updating Session.object_context (JSONB field).
        
        Options:
        1. Request bot-session team to add: PATCH /session/{id}/context
        2. Update via direct DB access (not recommended across services)
        3. Use event creation to trigger context updates indirectly
        4. Store context in ICE service's own cache/DB and sync periodically
        
        Recommended: Add PATCH /session/{session_id}/context to bot-session:
        Payload: {"context_updates": {"cart": {...}, "selections": {...}}}
        Implementation: Merge into Session.object_context JSONB field
        """
        raise NotImplementedError("update_session_context")
    
    async def close_session(self, session_id: str, reason: str) -> bool:
        """
        Close/terminate a user-bot session.
        
        Args:
            session_id: Session to close
            reason: Closure reason (timeout, user_exit, order_complete, error)
        
        Returns:
            True if closed successfully
        
        Endpoint: POST /session/{session_id}/close
        Payload: None (reason can be logged separately)
        Returns: {"session_id": str, "status": "closed", "closed_at": str}
        
        Implementation:
        - Sets Session.status = "closed"
        - Sets Session.closed_at timestamp
        - Calculates Session.duration_seconds
        - Completes any open SessionStateCycle records
        - Emits audit event: session_closed
        
        Note: The endpoint doesn't currently accept a 'reason' parameter.
        Consider adding it to the payload or logging separately.
        """
        try:
            # Log the closure reason for audit purposes
            logger.info(f"Closing session {session_id}, reason: {reason}")
            
            client = await self._get_client()
            response = await client.post(f"{self.base_url}/session/{session_id}/close")
            
            if response.status_code == 404:
                logger.warning(f"Session {session_id} not found for closure")
                return False
            
            if response.status_code == 200:
                return True
            
            logger.error(f"Failed to close session {session_id}: {response.status_code}")
            return False
            
        except Exception as e:
            logger.error(f"Error closing session {session_id}: {e}")
            return False
    
    async def get_active_sessions(self, phone_number: str) -> list[dict]:
        """
        Get all active sessions for a user.
        
        Args:
            phone_number: User's phone number
        
        Returns:
            List of active session objects
        
        Endpoint: GET /session/resolve?user_phone={phone}&status=active
        Alternative: GET /session/by-phone-platform/{user_phone}/{platform}
        
        The /session/resolve endpoint supports filtering by:
        - user_phone (optional)
        - bot_id (optional)
        - platform (optional)
        
        Returns: List of sessions matching filters
        
        For platform-specific queries, use:
        GET /session/by-phone-platform/{user_phone}/{platform}
        Returns: [{id, bot_id, status, session_mode}, ...]
        """
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/session/resolve",
                params={"user_phone": phone_number}
            )
            
            if response.status_code == 200:
                sessions = response.json()
                # Filter for active sessions only
                return [s for s in sessions if s.get("status") == "active"]
            
            logger.error(f"Failed to get active sessions for {phone_number}: {response.status_code}")
            return []
            
        except Exception as e:
            logger.error(f"Error getting active sessions for {phone_number}: {e}")
            return []
