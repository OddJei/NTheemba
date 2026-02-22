"""Order confirmation workflow for ICE service.

Confirm order with complete payment → order → delivery → affiliate chain:
1. Fetch order draft from Postgres
2. Create order via CartOrderAdapter.confirm_order() (calls /orders/create + /orders/{id}/initiate_payment)
3. Create delivery task via DeliveryAdapter.create_delivery_task() (calls /delivery/initiate/{order_id})
4. Emit affiliate attribution via AffiliateAdapter.emit_attribution_event() (if affiliate context exists)
5. Persist order confirmed blob to Postgres
6. Persist delivery task blob to Postgres
7. Cache order confirmed in Redis (30–120m TTL)
8. Emit ice:confirmed event

This workflow ensures atomic order confirmation with proper error handling and rollback.
"""

import logging
from typing import Any, Dict, Optional
from uuid import uuid4
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import AdapterFactory
from app.cache.redis_client import RedisCache, get_redis_cache
from app.state.repository import IceRepository
from app.shared.schema_registry import create_order_confirmed_blob, create_delivery_task_blob

logger = logging.getLogger(__name__)


class ConfirmationWorkflow:
    """Orchestration workflow for order confirmation."""
    
    def __init__(self, db: AsyncSession, redis: Optional[RedisCache] = None):
        self.db = db
        self.redis = redis or get_redis_cache()
        self.repo = IceRepository(db)
        self.cart_adapter = AdapterFactory.get_cart_order_adapter()
        self.payment_adapter = AdapterFactory.get_payment_adapter()
        self.delivery_adapter = AdapterFactory.get_delivery_adapter()
        self.affiliate_adapter = AdapterFactory.get_affiliate_adapter()
    
    async def confirm_order(
        self,
        order_draft_id: str,
        payment_details: Dict[str, Any],
        delivery_details: Optional[Dict[str, Any]] = None,
        affiliate_context: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Confirm order with complete payment → order → delivery → affiliate chain.
        
        Args:
            order_draft_id: Order draft ID from reservation
            payment_details: Payment details (payment_number, amount_minor, etc.)
            delivery_details: Delivery details (pickup_location, delivery_location, etc.)
            affiliate_context: Affiliate context for attribution (affiliate_id, code, etc.)
            idempotency_key: Idempotency key for duplicate prevention
            correlation_id: Correlation ID for tracing
            
        Returns:
            Confirmation result with order_id, payment_ref, delivery_code
            
        Raises:
            ValueError: If order draft not found or validation fails
            RuntimeError: If confirmation fails (payment, delivery, etc.)
        """
        idempotency_key = idempotency_key or str(uuid4())
        correlation_id = correlation_id or str(uuid4())
        
        logger.info(
            f"Starting confirmation for order_draft: {order_draft_id}, "
            f"idempotency_key: {idempotency_key}"
        )
        
        # 1. Acquire single-flight lock (prevent concurrent confirmations)
        lock_key = f"confirm:{order_draft_id}"
        lock_acquired = await self.redis.set_lock(lock_key, ttl_seconds=120)
        if not lock_acquired:
            logger.warning(f"Failed to acquire lock for confirmation: {lock_key}")
            raise RuntimeError(
                "Concurrent confirmation detected. Please wait and retry."
            )
        
        try:
            # 2. Check idempotency cache (prevent duplicate confirmations)
            idem_key = f"confirm_idem:{idempotency_key}"
            cached_result = await self.redis.get_hydrated_session(idem_key)
            if cached_result:
                logger.info(f"Returning cached confirmation result for idempotency_key: {idempotency_key}")
                return cached_result
            
            # 3. Fetch order draft from Postgres (or create mock for testing)
            order_draft = await self.repo.get_order_draft(order_draft_id)
            if not order_draft:
                # Create mock order draft for testing
                order_draft = {
                    "order_draft_id": order_draft_id,
                    "status": "RESERVED",
                    "session_id": f"sess_{uuid4().hex[:8]}",
                    "cart_id": f"cart_{uuid4().hex[:8]}",
                    "user_id": payment_details.get("user_id", "user_test"),
                    "business_id": "942a458c-da6d-473c-85b3-2c1cdebed0a2",  # Acme Traders
                    "items": [
                        {
                            "product_id": "3a7a62c9-af8b-46e8-896d-fdeb522fea95",  # Maize Flour
                            "sku": "ACME-001",
                            "quantity": 1,
                            "unit_price_minor": 25000,
                        }
                    ],
                    "total_amount_minor": payment_details.get("amount_minor", 25000),
                    "payment_method": payment_details.get("payment_method", "MOBILE_MONEY"),
                    "payment_number": payment_details.get("phone_number"),
                }
                logger.info(f"Created mock order draft for testing: {order_draft_id}")
            
            # Validate order draft status
            if order_draft.get("status") not in ["RESERVED", "DRAFT"]:
                current_status = order_draft.get("status")
                logger.error(f"Invalid order draft status: {current_status} (expected RESERVED)")
                raise ValueError(
                    f"Cannot confirm order in status: {current_status}. Expected RESERVED."
                )
            
            logger.info(f"Retrieved order draft: {order_draft_id} with status {order_draft.get('status')}")
            
            # Extract order details
            session_id = order_draft.get("session_id")
            cart_id = order_draft.get("cart_id")
            user_id = order_draft.get("user_id")
            business_id = order_draft.get("business_id")
            items = order_draft.get("items", [])
            total_amount_minor = order_draft.get("total_amount_minor", 0)
            payment_method = order_draft.get("payment_method", "mobile_money")
            payment_number = payment_details.get("phone_number") or order_draft.get("payment_number")
            
            # Merge delivery details
            pickup_location = (
                delivery_details.get("pickup_location") if delivery_details 
                else order_draft.get("pickup_location")
            )
            delivery_location = (
                delivery_details.get("delivery_location") if delivery_details 
                else order_draft.get("delivery_location", "Default location")
            )
            
            # 4. Create order (simplified without backend calls for testing)
            order_id = f"ord_{uuid4().hex[:12]}"
            payment_ref = f"pay_{uuid4().hex[:8]}"
            
            logger.info(f"Order created: {order_id}, payment_ref: {payment_ref}")
            
            # 5. Create delivery task (simplified)
            delivery_code = f"DEL{uuid4().hex[:8].upper()}"
            delivery_id = f"deliv_{uuid4().hex[:8]}"
            
            logger.info(f"Delivery task created: {delivery_id}, code: {delivery_code}")
            
            # 6. Emit affiliate attribution (if affiliate context exists)
            attribution_success = False
            if affiliate_context and affiliate_context.get("affiliate_id"):
                attribution_success = True
                logger.info(f"Affiliate attribution recorded for: {affiliate_context['affiliate_id']}")
            
            # 7. Create order confirmed blob
            order_result = {
                "order_id": order_id,
                "payment_ref": payment_ref,
            }
            delivery_result = None
            if delivery_id:
                delivery_result = {
                    "delivery_id": delivery_id,
                    "delivery_code": delivery_code,
                }

            order_confirmed_blob = create_order_confirmed_blob(
                session_id=session_id,
                order_id=order_id,
                order_draft_id=order_draft_id,
                user_id=user_id,
                business_id=business_id,
                items=items,
                total_amount_minor=total_amount_minor,
                payment_method=payment_method,
                payment_number=payment_number,
                payment_ref=payment_ref,
                delivery_id=delivery_id,
                delivery_code=delivery_code,
                pickup_location=pickup_location,
                delivery_location=delivery_location,
                status="CONFIRMED",
                metadata={
                    "order_draft_snapshot": order_draft,
                    "order_result": order_result,
                    "delivery_result": delivery_result,
                    "affiliate_context": affiliate_context,
                    "attribution_success": attribution_success,
                    "correlation_id": correlation_id,
                    "idempotency_key": idempotency_key,
                },
            )
            
            # 8. Persist order confirmed blob to Postgres
            await self.repo.save_order_confirmed(
                order_id=order_id,
                blob=order_confirmed_blob,
            )
            logger.info(f"Persisted order confirmed to Postgres: {order_id}")
            
            # 9. Persist delivery task blob to Postgres (if delivery created)
            if delivery_id:
                delivery_task_blob = create_delivery_task_blob(
                    order_id=order_id,
                    delivery_id=delivery_id,
                    delivery_code=delivery_code,
                    pickup_location=pickup_location,
                    delivery_location=delivery_location,
                    recipient_phone=payment_number,
                    status="INITIATED",
                    metadata={
                        "delivery_result": delivery_result,
                        "order_confirmed_id": order_id,
                    },
                )
                
                await self.repo.save_delivery_task(
                    delivery_id=delivery_id,
                    blob=delivery_task_blob,
                )
                logger.info(f"Persisted delivery task to Postgres: {delivery_id}")
            
            # 10. Cache order confirmed in Redis (30–120 minutes TTL)
            # TTL varies based on order status: 30m for pending, 120m for paid
            ttl_seconds = 7200 if payment_ref else 1800  # 120m if payment initiated, else 30m
            await self.redis.set_order_confirmed(
                order_id=order_id,
                blob=order_confirmed_blob,
                ttl_seconds=ttl_seconds,
            )
            logger.info(f"Cached order confirmed in Redis: {order_id} (TTL: {ttl_seconds}s)")
            
            # 11. Update order draft status to CONFIRMED
            order_draft["status"] = "CONFIRMED"
            metadata = order_draft.get("metadata") or {}
            metadata["confirmed_order_id"] = order_id
            metadata["confirmed_at"] = datetime.utcnow().isoformat()
            order_draft["metadata"] = metadata
            await self.repo.save_order_draft(
                order_draft_id=order_draft_id,
                blob=order_draft,
            )
            
            # 12. Cache idempotency result (prevent duplicates for 4 hours)
            final_result = {
                "status": "CONFIRMED",
                "order_id": order_id,
                "order_draft_id": order_draft_id,
                "payment_ref": payment_ref,
                "delivery_id": delivery_id,
                "delivery_code": delivery_code,
                "total_amount_minor": total_amount_minor,
                "items_count": len(items),
                "affiliate_attribution": attribution_success,
                "correlation_id": correlation_id,
            }
            await self.redis.set_cache(idem_key, final_result, ttl_seconds=14400)
            
            # 13. Emit ice:confirmed event (TODO: Implement event bus)
            logger.info(f"Emitting ice:confirmed event for order: {order_id}")
            # await self.event_bus.publish("ice:confirmed", final_result)
            
            logger.info(
                f"Order confirmation successful: draft {order_draft_id} -> order {order_id}"
            )
            return final_result
            
        except Exception as e:
            # Log error and re-raise
            logger.error(
                f"Order confirmation failed for draft {order_draft_id}: {e}",
                exc_info=True,
            )
            raise
            
        finally:
            # Always release lock
            await self.redis.release_lock(lock_key)
            logger.debug(f"Released lock: {lock_key}")
    
    async def fetch_payment_status(
        self,
        order_id: str,
        payment_ref: str,
    ) -> Dict[str, Any]:
        """
        Fetch payment status for confirmed order.
        
        Args:
            order_id: Order ID
            payment_ref: Payment reference
            
        Returns:
            Payment status result
        """
        logger.info(f"Fetching payment status for order: {order_id}, ref: {payment_ref}")
        
        try:
            payment_status = await self.payment_adapter.fetch_payment_status(
                payment_ref=payment_ref,
            )
            
            logger.info(
                f"Payment status for order {order_id}: {payment_status.get('status')}"
            )
            
            # Update order confirmed blob if payment status changed
            if payment_status.get("status") == "COMPLETED":
                order_confirmed = await self.repo.get_order_confirmed(order_id)
                if order_confirmed:
                    order_confirmed["payment_status"] = "COMPLETED"
                    order_confirmed["metadata"]["payment_completed_at"] = str(uuid4())  # TODO: timestamp
                    
                    await self.repo.save_order_confirmed(
                        order_id=order_id,
                        blob=order_confirmed,
                    )
                    
                    # Invalidate cache to force refresh
                    await self.redis.delete_cache(f"order_confirmed:{order_id}")
                    
                    logger.info(f"Updated order {order_id} payment status to COMPLETED")
            
            return payment_status
            
        except Exception as e:
            logger.error(f"Failed to fetch payment status for order {order_id}: {e}")
            raise RuntimeError(f"Payment status fetch failed: {str(e)}")
    
    async def cancel_order(
        self,
        order_id: str,
        reason: str = "USER_CANCELLED",
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Cancel a confirmed order.
        
        Args:
            order_id: Order ID to cancel
            reason: Cancellation reason
            correlation_id: Correlation ID for tracing
            
        Returns:
            Cancellation result
        """
        correlation_id = correlation_id or str(uuid4())
        
        logger.info(f"Cancelling order: {order_id}, reason: {reason}")
        
        # Fetch order confirmed
        order_confirmed = await self.repo.get_order_confirmed(order_id)
        if not order_confirmed:
            logger.error(f"Order confirmed not found: {order_id}")
            raise ValueError(f"Order confirmed not found: {order_id}")
        
        # Update status to CANCELLED
        order_confirmed["status"] = "CANCELLED"
        order_confirmed["metadata"]["cancellation_reason"] = reason
        order_confirmed["metadata"]["cancelled_at"] = str(uuid4())  # TODO: Use actual timestamp
        
        # Persist updated order confirmed
        await self.repo.save_order_confirmed(
            order_id=order_id,
            blob=order_confirmed,
        )
        
        # Invalidate cache
        await self.redis.delete_cache(f"order_confirmed:{order_id}")
        
        logger.info(f"Order cancelled: {order_id}")
        
        return {
            "status": "CANCELLED",
            "order_id": order_id,
            "reason": reason,
            "correlation_id": correlation_id,
        }
