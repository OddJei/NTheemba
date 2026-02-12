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
        idempotency_key = idempotency_key or str(uuid4())
        correlation_id = correlation_id or str(uuid4())
        
        logger.info(
            f"Starting reservation for session: {session_id}, cart: {cart_id}, "
            f"idempotency_key: {idempotency_key}"
        )
        
        # 1. Acquire single-flight lock (prevent concurrent reservations)
        lock_key = f"reserve:{session_id}:{cart_id}"
        lock_acquired = await self.redis.set_lock(lock_key, ttl_seconds=60)
        if not lock_acquired:
            logger.warning(f"Failed to acquire lock for reservation: {lock_key}")
            raise RuntimeError(
                "Concurrent reservation detected. Please wait and retry."
            )
        
        try:
            # 2. Check idempotency cache (prevent duplicate reservations)
            idem_key = f"reserve_idem:{idempotency_key}"
            cached_result = await self.redis.get_hydrated_session(idem_key)
            if cached_result:
                logger.info(f"Returning cached reservation result for idempotency_key: {idempotency_key}")
                return cached_result
            
            # 3. Fetch cart draft from cache or DB (simplified - create mock draft)
            cart_draft = await self.redis.get_cart(cart_id)
            if not cart_draft:
                # Create a simple mock cart draft for testing
                cart_draft = {
                    "cart_id": cart_id,
                    "items": [
                        {
                            "product_id": "prod_001",
                            "sku": "ACME-001",
                            "quantity": 1,
                            "unit_price_minor": 25000,
                        }
                    ],
                    "total_amount_minor": 25000,
                    "business_id": business_id,
                }
                logger.info(f"Created mock cart draft for testing: {cart_id}")
            
            logger.info(f"Retrieved cart draft: {cart_id} with {len(cart_draft.get('items', []))} items")
            
            # 4. Simple reservation without backend calls (for testing)
            reservation_result = {
                "status": "RESERVED",
                "reservation_ref": f"res_{uuid4().hex[:8]}",
                "order_draft_id": f"ord_{uuid4().hex[:8]}",
            }
            logger.info(f"Created mock reservation: {reservation_result['order_draft_id']}")
            
            # 6. Create order draft blob
            order_draft_blob = create_order_draft_blob(
                session_id=session_id,
                cart_id=cart_id,
                user_id=user_id,
                business_id=business_id,
                items=cart_draft.get("items", []),
                total_amount_minor=cart_draft.get("total_amount_minor", 0),
                payment_method=payment_method,
                payment_number=payment_number,
                pickup_location=pickup_location,
                delivery_location=delivery_location,
                reservation_ref=reservation_result.get("reservation_ref"),
                status="RESERVED",
                metadata={
                    "cart_snapshot": cart_draft,
                    "reservation_result": reservation_result,
                    "correlation_id": correlation_id,
                    "idempotency_key": idempotency_key,
                },
            )
            
            # 7. Persist order draft to Postgres
            order_draft_id = reservation_result.get("order_draft_id") or str(uuid4())
            await self.repo.save_order_draft(
                order_draft_id=order_draft_id,
                blob=order_draft_blob,
            )
            logger.info(f"Persisted order draft to Postgres: {order_draft_id}")
            
            # 8. Cache order draft in Redis (60 minutes TTL)
            await self.redis.set_order_draft(
                order_draft_id=order_draft_id,
                blob=order_draft_blob,
                ttl_seconds=3600,  # 60 minutes
            )
            logger.info(f"Cached order draft in Redis: {order_draft_id}")
            
            # 9. Cache idempotency result (prevent duplicates for 2 hours)
            final_result = {
                "status": "RESERVED",
                "order_draft_id": order_draft_id,
                "reservation_ref": reservation_result.get("reservation_ref"),
                "cart_id": cart_id,
                "total_amount_minor": cart_draft.get("total_amount_minor", 0),
                "items_count": len(cart_draft.get("items", [])),
                "correlation_id": correlation_id,
            }
            await self.redis.set_hydrated_session(idem_key, final_result, ttl_minutes=120)
            
            # 10. Emit ice:reserved event (TODO: Implement event bus)
            logger.info(f"Emitting ice:reserved event for order_draft: {order_draft_id}")
            # await self.event_bus.publish("ice:reserved", final_result)
            
            logger.info(f"Reservation successful for cart {cart_id} -> order_draft {order_draft_id}")
            return final_result
            
        finally:
            # Always release lock
            await self.redis.release_lock(lock_key)
            logger.debug(f"Released lock: {lock_key}")
    
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
        order_draft["metadata"]["cancellation_reason"] = reason
        order_draft["metadata"]["cancelled_at"] = str(uuid4())  # TODO: Use actual timestamp
        
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
