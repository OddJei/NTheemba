"""
Bot Session Service Adapter

Handles session state persistence, Redis streams, and cache operations
via the bot-session backend service (port 8540).

ENDPOINT MAPPING (from services/bot-session/src/app/main.py):
-------------------------------------------------------------
Bot Endpoints:
- POST   /bot/create                       → Create new bot
- GET    /bot/by-phone/{phone}             → Get bot by phone number

Session Endpoints:
- POST   /session/create                   → Create/reactivate session
- GET    /session/{session_id}             → Get session by ID
- POST   /session/{session_id}/close       → Close session
- GET    /session/resolve                  → Resolve session by user_phone/bot_id/platform
- GET    /session/by-phone-platform/{user_phone}/{platform} → Get sessions by phone+platform
- GET    /session/{session_id}/cycles      → Get session state cycles (affiliate attribution)

Event Endpoints:
- POST   /event/create                     → Create event (message/action)
- PUT    /event/{event_id}/update          → Update event
- GET    /event/{event_id}                 → Get event by ID
- GET    /event/session/{session_id}       → Get events for session
- GET    /event/phone/{user_phone}         → Get events for user

Admin Endpoints:
- GET    /admin/session/{session_id}/full  → Full session details (session+cycles+events)

Utility:
- GET    /health                           → Health check

NOTES:
- Session model includes `state` field (chat → cart → order → payment → delivery → closed)
- SessionStateCycle tracks affiliate attribution per lifecycle stage
- `object_context` field stores JSONB data (cart, selections, etc.)
- Auth middleware requires Bearer token (except public endpoints)
- Optimistic locking via `version` field on Bot model
"""
import os
from typing import Optional
import httpx
import logging
from .base import BotSessionAdapter

logger = logging.getLogger(__name__)


class BotSessionServiceAdapter(BotSessionAdapter):
    """
    Adapter for bot-session service infrastructure layer.
    
    Responsibilities:
    - Low-level session storage operations
    - Redis stream publishing/subscribing
    - Cache management
    - Event tracking
    
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
        
        logger.info(f"BotSessionServiceAdapter initialized with base_url={self.base_url}, timeout={self.timeout}s")
    
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
        Check if bot-session service is reachable.
        
        Endpoint: GET /health
        Returns: {"status": "ok"}
        """
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
    
    async def persist_session(self, session_id: str, session_data: dict) -> bool:
        """
        Persist session data to bot-session service.
        
        Args:
            session_id: Unique session identifier
            session_data: Session state (schema-versioned JSONB)
        
        Returns:
            True if persisted successfully
        
        NOTE: The actual bot-session service uses Session.object_context (JSONB)
        for storing arbitrary session data. This is typically updated via
        the Session model directly, not a dedicated endpoint.
        
        For ICE purposes, consider storing hydrated session blobs in:
        - Session.object_context (via UPDATE to sessions table)
        - Or a dedicated Redis cache key pattern: cache:session:{session_id}
        
        If using database storage, coordinate with bot-session team to add
        PATCH /session/{session_id}/context endpoint.
        """
        # TODO: Coordinate with bot-session team to add PATCH /session/{id}/context
        # For now, this would require direct DB access or storing in ICE's own cache
        logger.warning(
            f"persist_session called for {session_id} but no endpoint exists. "
            "Consider storing in ICE cache or requesting PATCH /session/{{id}}/context endpoint."
        )
        return False
    
    async def fetch_session(self, session_id: str) -> Optional[dict]:
        """
        Retrieve session data from bot-session service.
        
        Args:
            session_id: Unique session identifier
        
        Returns:
            Session data dict or None if not found
        
        Endpoint: GET /session/{session_id}
        Returns: {
            "id": str,
            "user_phone": str,
            "bot_id": str,
            "platform": str,
            "session_mode": str,  # public/registered/customer/staff
            "status": str,  # active/inactive/closed
            "last_event_id": str
        }
        
        Note: This returns basic session metadata. For full session including
        object_context and cycles, use GET /admin/session/{session_id}/full
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/session/{session_id}")
            
            if response.status_code == 404:
                return None
            
            if response.status_code == 200:
                return response.json()
            
            logger.error(f"Failed to fetch session {session_id}: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error fetching session {session_id}: {e}")
            return None
    
    async def publish_to_stream(self, stream_key: str, payload: dict) -> str:
        """
        Publish message to Redis stream via bot-session.
        
        Args:
            stream_key: Redis stream key (e.g., "ice:hydrated", "oob:audit")
            payload: Message payload
        
        Returns:
            Message ID from Redis XADD
        
        NOTE: The bot-session service does NOT currently expose dedicated
        stream publishing endpoints. Redis stream operations are handled
        internally or via direct Redis client.
        
        For ICE service, consider:
        1. Direct Redis client (preferred for performance)
        2. Request bot-session team to add POST /streams/publish endpoint
        3. Use event creation (POST /event/create) which may trigger streams
        """
        # TODO: Implement with direct Redis client (redis.asyncio)
        # from redis.asyncio import Redis
        # redis = Redis.from_url(os.getenv("REDIS_URL"))
        # message_id = await redis.xadd(stream_key, payload)
        logger.warning(
            f"publish_to_stream called for {stream_key} but no HTTP endpoint exists. "
            "Use direct Redis client (redis.asyncio) for stream operations."
        )
        raise NotImplementedError("Use direct Redis client for stream publishing")
    
    async def subscribe_to_stream(
        self, 
        stream_key: str, 
        consumer_group: str, 
        consumer_name: str, 
        count: int = 10
    ) -> list[dict]:
        """
        Read messages from Redis stream via bot-session.
        
        Args:
            stream_key: Redis stream key
            consumer_group: Consumer group name
            consumer_name: Consumer name within group
            count: Max messages to read
        
        Returns:
            List of stream messages
        
        NOTE: The bot-session service does NOT currently expose dedicated
        stream consumption endpoints. Redis streams are consumed internally.
        
        For ICE service, use direct Redis client (redis-py with asyncio)
        to consume from streams like:
        - ingress:incoming
        - bot:lane:{type}
        - intent:requests/results
        - reply:requests
        - outbound:requests
        - ice:preload, ice:hydrated
        - oob:audit
        """
        # TODO: Implement with direct Redis client (redis.asyncio)
        # from redis.asyncio import Redis
        # redis = Redis.from_url(os.getenv("REDIS_URL"))
        # messages = await redis.xreadgroup(
        #     groupname=consumer_group,
        #     consumername=consumer_name,
        #     streams={stream_key: '>'},
        #     count=count
        # )
        logger.warning(
            f"subscribe_to_stream called for {stream_key} but no HTTP endpoint exists. "
            "Use direct Redis client (redis.asyncio) for stream operations."
        )
        raise NotImplementedError("Use direct Redis client for stream consumption")
