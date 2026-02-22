"""Reservation workflow for ICE service.

Reserve inventory atomically:
1. Fetch cart draft from Redis/Postgres
2. Call CartOrderAdapter.reserve_items() (calls /cart/{id}/checkout)
3. Handle OUT_OF_STOCK response (negative cache)
4. Persist order draft blob to Postgres
5. Cache order draft in Redis (60m TTL)
6. Emit ice:reserved event

This workflow ensures atomic reservation with proper locking and caching.
"""

import logging
from typing import Any, Dict, Optional
from uuid import uuid4
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import AdapterFactory
from app.cache.redis_client import RedisCache, get_redis_cache
from app.state.repository import IceRepository
from app.shared.schema_registry import create_order_draft_blob

logger = logging.getLogger(__name__)


class ReservationWorkflow:
    """Orchestration workflow for inventory reservation."""
    
    def __init__(self, db: AsyncSession, redis: Optional[RedisCache] = None):
        self.db = db
        self.redis = redis or get_redis_cache()
        self.repo = IceRepository(db)
        self.cart_adapter = AdapterFactory.get_cart_order_adapter()
    
    async def reserve_inventory(
        self,
        session_id: str,
        cart_id: str,
        user_id: str,
        business_id: str,
        payment_method: str = "mobile_money",
        payment_number: Optional[str] = None,
        pickup_location: Optional[str] = None,
        delivery_location: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Reserve inventory atomically.
        
        Args:
            session_id: Session ID
            cart_id: Cart ID to reserve
            user_id: User ID
            business_id: Business ID
            payment_method: Payment method (default: mobile_money)
            payment_number: Payment phone number (required for mobile_money)
            pickup_location: Pickup location for delivery
            delivery_location: Delivery location
            idempotency_key: Idempotency key for duplicate prevention
            correlation_id: Correlation ID for tracing
            
        Returns:
            Reservation result with status and order draft
            
        Raises:
            ValueError: If reservation fails (OUT_OF_STOCK, validation error)
            RuntimeError: If lock acquisition fails or backend errors
        """
        # Reservation responsibility removed from ICE: Cart service handles
        # item reservations and checkout. Keep a simple delegation result so
        # orchestration callers know to use the Cart service instead.
        logger.info("Reservation logic disabled in ICE; delegate to Cart service for cart_id=%s", cart_id)
        return {
            "status": "DELEGATED",
            "message": "Reservations are handled by the Cart service. Use Cart endpoints to manage reservations.",
            "cart_id": cart_id,
        }
    
    async def cancel_reservation(
        self,
        order_draft_id: str,
        reason: str = "USER_CANCELLED",
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Cancel a reservation (mark order draft as cancelled).
        
        Args:
            order_draft_id: Order draft ID to cancel
            reason: Cancellation reason
            correlation_id: Correlation ID for tracing
            
        Returns:
            Cancellation result
        """
        correlation_id = correlation_id or str(uuid4())
        
        logger.info(f"Cancelling reservation: {order_draft_id}, reason: {reason}")
        
        # Fetch order draft
        order_draft = await self.repo.get_order_draft(order_draft_id)
        if not order_draft:
            logger.error(f"Order draft not found: {order_draft_id}")
            raise ValueError(f"Order draft not found: {order_draft_id}")
        
        # Update status to CANCELLED
        order_draft["status"] = "CANCELLED"
        # Ensure metadata dict exists
        metadata = order_draft.get("metadata") or {}
        metadata["cancellation_reason"] = reason
        metadata["cancelled_at"] = datetime.utcnow().isoformat()
        order_draft["metadata"] = metadata
        
        # Persist updated order draft
        await self.repo.save_order_draft(
            order_draft_id=order_draft_id,
            blob=order_draft,
        )
        
        # Invalidate cache
        await self.redis.set_order_draft(f"order_draft:{order_draft_id}", None, ttl_seconds=1)
        
        logger.info(f"Reservation cancelled: {order_draft_id}")
        
        return {
            "status": "CANCELLED",
            "order_draft_id": order_draft_id,
            "reason": reason,
            "correlation_id": correlation_id,
        }
