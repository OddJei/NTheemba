"""Base adapter interfaces for ICE backend integrations."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAdapter(ABC):
    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if downstream is reachable."""
        raise NotImplementedError


class BotSessionAdapter(BaseAdapter):
    """Adapter for bot-session service (session state, streams, cache)."""
    
    @abstractmethod
    async def persist_session(self, session_id: str, session_data: Dict[str, Any]) -> bool:
        """Persist session data to bot-session service."""
        raise NotImplementedError
    
    @abstractmethod
    async def fetch_session(self, session_id: str) -> Dict[str, Any] | None:
        """Retrieve session data from bot-session service."""
        raise NotImplementedError
    
    @abstractmethod
    async def publish_to_stream(self, stream_key: str, payload: Dict[str, Any]) -> str:
        """Publish message to Redis stream via bot-session."""
        raise NotImplementedError
    
    @abstractmethod
    async def subscribe_to_stream(self, stream_key: str, consumer_group: str, consumer_name: str, count: int = 10) -> list[Dict[str, Any]]:
        """Read messages from Redis stream via bot-session."""
        raise NotImplementedError


class UserBotSessionAdapter(BaseAdapter):
    """Adapter for user-bot conversation session interactions."""
    
    @abstractmethod
    async def create_session(self, phone_number: str, business_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new user-bot conversation session."""
        raise NotImplementedError
    
    @abstractmethod
    async def get_session_state(self, session_id: str) -> Dict[str, Any] | None:
        """Get current session state including conversation context."""
        raise NotImplementedError
    
    @abstractmethod
    async def update_session_context(self, session_id: str, context_updates: Dict[str, Any]) -> bool:
        """Update session context (cart, selections, conversation state)."""
        raise NotImplementedError
    
    @abstractmethod
    async def close_session(self, session_id: str, reason: str) -> bool:
        """Close/terminate a user-bot session."""
        raise NotImplementedError
    
    @abstractmethod
    async def get_active_sessions(self, phone_number: str) -> list[Dict[str, Any]]:
        """Get all active sessions for a user."""
        raise NotImplementedError


class CatalogAdapter(BaseAdapter):
    @abstractmethod
    async def fetch_product_snapshot(self, business_id: str, product_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def fetch_catalog_index(self, business_id: str) -> Dict[str, Any]:
        raise NotImplementedError


class CartOrderAdapter(BaseAdapter):
    @abstractmethod
    async def create_or_update_draft(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def reserve_items(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def confirm_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class PaymentAdapter(BaseAdapter):
    @abstractmethod
    async def create_payment_intent(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def fetch_payment_status(self, payment_ref: str) -> Dict[str, Any]:
        raise NotImplementedError


class DeliveryAdapter(BaseAdapter):
    @abstractmethod
    async def validate_delivery(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def create_delivery_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class AffiliateAdapter(BaseAdapter):
    @abstractmethod
    async def hydrate_affiliate_context(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def emit_attribution_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class MsmeAdapter(BaseAdapter):
    @abstractmethod
    async def fetch_business_profile(self, business_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def fetch_business_policies(self, business_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_business_by_phone(self, phone_number: str) -> Dict[str, Any]:
        """Lookup business by phone number."""
        raise NotImplementedError

    @abstractmethod
    async def get_user_by_phone(self, phone_number: str) -> Dict[str, Any]:
        """Lookup user by phone number."""
        raise NotImplementedError
