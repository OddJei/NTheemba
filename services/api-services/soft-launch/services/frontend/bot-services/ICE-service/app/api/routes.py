"""FastAPI routes for ICE service."""

import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.api.schemas import (
    HydrateSessionRequest,
    HydrateSessionResponse,
    MessageLogRequest,
    MessageLogResponse,
    ReserveRequest,
    ReserveResponse,
    ConfirmRequest,
    ConfirmResponse,
    PaymentStatusResponse,
    CancelRequest,
    CancelResponse,
    HealthCheckResponse,
    ReadinessCheckResponse,
)
from app.cache.redis_client import get_redis_cache, RedisCache
from app.state.repository import get_db, AsyncSessionLocal, IceRepository
from app.orchestration.hydrate import HydrationWorkflow
from app.orchestration.reserve import ReservationWorkflow
from app.orchestration.confirm import ConfirmationWorkflow


logger = logging.getLogger(__name__)


# ============================================================================
# Health Check Routes
# ============================================================================

health_router = APIRouter(tags=["Health"])


@health_router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    try:
        redis = get_redis_cache()
        is_healthy = await redis.health_check()
        health_info = {"connected": is_healthy}
        return HealthCheckResponse(status="ok", redis=health_info)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")


@health_router.get("/ready", response_model=ReadinessCheckResponse)
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness check endpoint."""
    try:
        # Check database
        await db.execute(text("SELECT 1"))
        logger.info("Readiness check passed")
        return ReadinessCheckResponse(status="ready")
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Not ready")


# ============================================================================
# Hydration Routes
# ============================================================================

hydration_router = APIRouter(prefix="/api/v1", tags=["Hydration"])


# ============================================================================
# Message Log Routes
# ============================================================================

messages_router = APIRouter(prefix="/api/v1", tags=["Messages"])


def _parse_iso(dt: Optional[str]) -> Optional[datetime]:
    if not dt:
        return None
    try:
        value = dt.replace("Z", "+00:00")
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid datetime format: {dt}") from exc


@hydration_router.post(
    "/hydrate/session",
    response_model=HydrateSessionResponse,
    summary="Hydrate session context for bot-ingress",
)
async def hydrate_session(
    request: HydrateSessionRequest,
    idempotency_key: Optional[str] = Header(None),
    redis: RedisCache = Depends(lambda: get_redis_cache()),
):
    """
    Hydrate session context by composing data from all backend adapters.
    
    This is the primary endpoint called by bot-ingress when cache misses
    or when fresh hydration is required.
    
    **Request:**
    - `event_id`: Unique event ID (required for idempotency)
    - `session_id`: Session to hydrate
    - `user_id`: Optional user ID
    - `bot_id`: Optional bot ID
    - `required_blobs`: List of blob types to include (default: session, order_draft, bot_meta)
    
    **Response:**
    - `hydrated`: bool indicating success
    - `session_blob`: Hydrated session context
    - `order_draft_blob`: Current order draft (if exists)
    - `bot_meta_blob`: Bot metadata
    
    **Idempotency:**
    - Use `idempotency_key` header or `event_id` for duplicate detection
    - Returns same response for duplicate requests
    """
    try:
        # Use idempotency_key header or event_id
        idem_key = idempotency_key or request.event_id
        
        # Check idempotency cache using correct Redis method
        cached_response = await redis.get_hydrated_session(idem_key)
        if cached_response:
            logger.info(f"Returning cached hydration for event: {request.event_id}")
            return HydrateSessionResponse(**cached_response)
        
        # Create a minimal DB session for the workflow
        async with AsyncSessionLocal() as db:
            # Instantiate hydration workflow
            workflow = HydrationWorkflow(db, redis)

            customer_phone = request.from_number or request.user_phone or ""
            business_phone = request.to_number or ""
            
            # Hydrate session (phone-only mode: no business_id needed)
            logger.info(f"Hydrating session: {request.session_id}, event: {request.event_id}")
            session_blob = await workflow.hydrate_session(
                session_id=request.session_id,
                phone_number=customer_phone,
                business_id=request.business_id or "",
                business_phone=business_phone,
                platform=request.platform,
                bot_id=request.bot_id,
                bot_type=request.bot_type,
                affiliate_code=None,
                correlation_id=request.event_id,
            )
        
        # Enrich with request metadata if blob was returned
        if session_blob and isinstance(session_blob, dict):
            if request.bot_id:
                session_blob["bot_id"] = request.bot_id
            if request.platform:
                session_blob["platform"] = request.platform
            if request.bot_type:
                session_blob["bot_type"] = request.bot_type
        
        # Extract order_draft from metadata if present
        order_draft = None
        if session_blob and isinstance(session_blob, dict):
            metadata = session_blob.get("metadata", {})
            order_draft = metadata.get("order_draft")
        
        # Build response (session_blob contains the full blob from create_session_blob)
        response = HydrateSessionResponse(
            hydrated=bool(session_blob),
            session_blob=session_blob if session_blob else None,
            order_draft_blob=order_draft,
            bot_meta_blob=None,  # TODO: Implement bot conversation metadata
            user_blob=None,
        )
        
        # Cache response for idempotency (1 hour)
        await redis.set_hydrated_session(
            idem_key,
            response.model_dump(),
            ttl_minutes=60,
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Hydration error: {e}", exc_info=True)
        return HydrateSessionResponse(
            hydrated=False,
            error={
                "code": "ICE_HYDRATION_FAILED",
                "message": str(e),
            }
        )


@messages_router.post(
    "/messages/log",
    response_model=MessageLogResponse,
    summary="Upsert incoming/outgoing message log",
)
async def upsert_message_log(
    payload: MessageLogRequest,
    db: AsyncSession = Depends(get_db),
):
    repo = IceRepository(db)
    try:
        log = await repo.upsert_message_log(
            correlation_id=payload.correlation_id,
            session_id=payload.session_id,
            business_id=payload.business_id,
            user_phone=payload.user_phone,
            bot_phone=payload.bot_phone,
            incoming_message=payload.incoming_message,
            incoming_payload=payload.incoming_payload,
            incoming_at=_parse_iso(payload.incoming_at),
            outgoing_message=payload.outgoing_message,
            outgoing_payload=payload.outgoing_payload,
            outgoing_status=payload.outgoing_status,
            outgoing_at=_parse_iso(payload.outgoing_at),
            provider_message_id=payload.provider_message_id,
            error_message=payload.error_message,
        )
        await repo.commit()

        return MessageLogResponse(
            id=str(log.id),
            correlation_id=log.correlation_id,
            session_id=log.session_id,
            status=log.outgoing_status,
        )
    except HTTPException:
        await repo.rollback()
        raise
    except Exception as e:
        await repo.rollback()
        logger.error(f"Message log upsert failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to upsert message log")


# ============================================================================
# Order Routes
# ============================================================================

orders_router = APIRouter(prefix="/api/v1", tags=["Orders"])


@orders_router.post(
    "/reserve",
    response_model=ReserveResponse,
    summary="Reserve inventory atomically",
)
async def reserve(
    request: ReserveRequest,
    db: AsyncSession = Depends(get_db),
    redis: RedisCache = Depends(lambda: get_redis_cache()),
):
    """
    Atomically reserve inventory and create order draft.
    
    **Request:**
    - `session_id`, `cart_id`, `user_id`, `business_id`: Required identifiers
    - `payment_method`: Payment method (default: mobile_money)
    - `payment_number`: Payment number for mobile money
    - `idempotency_key`: For duplicate prevention
    
    **Response:**
    - `status`: RESERVED on success
    - `order_draft_id`: ID of created draft
    - `reservation_ref`: Reference for tracking
    
    **Error Codes:**
    - `ICE_RESERVE_OUT_OF_STOCK`: One or more items unavailable
    - `ICE_RESERVE_CONCURRENT_OP`: Concurrent reservation in progress
    
    **Idempotency:**
    - Same `idempotency_key` returns same result (2 hour window)
    """
    try:
        workflow = ReservationWorkflow(db, redis)
        
        result = await workflow.reserve_inventory(
            session_id=request.session_id,
            cart_id=request.cart_id,
            user_id=request.user_id,
            business_id=request.business_id,
            payment_method=request.payment_method,
            payment_number=request.payment_number,
            idempotency_key=request.idempotency_key,
        )
        
        return ReserveResponse(
            status="RESERVED",
            order_draft_id=result.get("order_draft_id"),
            reservation_ref=result.get("reservation_ref"),
        )
        
    except ValueError as e:
        logger.warning(f"Reserve validation error: {e}")
        error_code = "ICE_RESERVE_OUT_OF_STOCK" if "out of stock" in str(e).lower() else "ICE_RESERVE_VALIDATION_FAILED"
        return ReserveResponse(
            status="FAILED",
            error_code=error_code,
            error_message=str(e),
        )
    except RuntimeError as e:
        logger.warning(f"Reserve concurrency error: {e}")
        return ReserveResponse(
            status="FAILED",
            error_code="ICE_RESERVE_CONCURRENT_OP",
            error_message=str(e),
        )
    except Exception as e:
        logger.error(f"Reserve error: {e}", exc_info=True)
        return ReserveResponse(
            status="FAILED",
            error_code="ICE_RESERVE_FAILED",
            error_message=str(e),
        )


@orders_router.post(
    "/confirm",
    response_model=ConfirmResponse,
    summary="Confirm order with payment/delivery/affiliate chain",
)
async def confirm(
    request: ConfirmRequest,
    db: AsyncSession = Depends(get_db),
    redis: RedisCache = Depends(lambda: get_redis_cache()),
):
    """
    Confirm order by orchestrating: order creation → payment → delivery → affiliate attribution.
    
    **Request:**
    - `order_draft_id`: ID from reserve endpoint
    - `payment_details`: Payment info (method, phone, amount, etc.)
    - `delivery_details`: Optional delivery info
    - `affiliate_context`: Optional affiliate info
    - `idempotency_key`: For duplicate prevention
    
    **Response:**
    - `status`: CONFIRMED on success
    - `order_id`: Created order ID
    - `payment_ref`: Payment reference for tracking
    - `delivery_id`: Delivery task ID
    - `delivery_code`: Delivery tracking code
    - `attribution_success`: Whether affiliate attribution succeeded
    
    **Error Codes:**
    - `ICE_CONFIRM_DRAFT_NOT_FOUND`: Order draft doesn't exist
    - `ICE_CONFIRM_INVALID_STATUS`: Draft not in RESERVED state
    - `ICE_CONFIRM_PAYMENT_FAILED`: Payment initiation failed
    
    **Note:**
    - Delivery and affiliate failures are non-blocking (logged but don't fail confirmation)
    - Response includes `attribution_success` flag
    
    **Idempotency:**
    - Same `idempotency_key` returns same result (4 hour window)
    """
    try:
        workflow = ConfirmationWorkflow(db, redis)
        
        result = await workflow.confirm_order(
            order_draft_id=request.order_draft_id,
            payment_details=request.payment_details,
            delivery_details=request.delivery_details,
            affiliate_context=request.affiliate_context,
            idempotency_key=request.idempotency_key,
        )
        
        return ConfirmResponse(
            status="CONFIRMED",
            order_id=result.get("order_id"),
            payment_ref=result.get("payment_ref"),
            delivery_id=result.get("delivery_id"),
            delivery_code=result.get("delivery_code"),
            attribution_success=result.get("attribution_success"),
        )
        
    except ValueError as e:
        logger.warning(f"Confirm validation error: {e}")
        error_code = "ICE_CONFIRM_DRAFT_NOT_FOUND"
        if "status" in str(e).lower():
            error_code = "ICE_CONFIRM_INVALID_STATUS"
        return ConfirmResponse(
            status="FAILED",
            error_code=error_code,
            error_message=str(e),
        )
    except RuntimeError as e:
        logger.warning(f"Confirm backend error: {e}")
        return ConfirmResponse(
            status="FAILED",
            error_code="ICE_CONFIRM_PAYMENT_FAILED" if "payment" in str(e).lower() else "ICE_CONFIRM_FAILED",
            error_message=str(e),
        )
    except Exception as e:
        logger.error(f"Confirm error: {e}", exc_info=True)
        return ConfirmResponse(
            status="FAILED",
            error_code="ICE_CONFIRM_FAILED",
            error_message=str(e),
        )


@orders_router.get(
    "/orders/{order_id}/payment_status",
    response_model=PaymentStatusResponse,
    summary="Fetch payment status for confirmed order",
)
async def get_payment_status(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    redis: RedisCache = Depends(lambda: get_redis_cache()),
):
    """
    Fetch current payment status for a confirmed order.
    
    **Path Parameters:**
    - `order_id`: Order ID to check
    
    **Response:**
    - `payment_status`: Current status (PENDING, COMPLETED, FAILED, etc.)
    - `payment_ref`: Payment reference
    - `amount_minor`: Amount in minor units
    - `currency`: Currency code
    - `updated_at`: Last update timestamp
    
    **Polling:**
    - This endpoint can be polled to check payment progress
    - Respects idempotency: repeated calls return cached status
    """
    try:
        workflow = ConfirmationWorkflow(db, redis)
        
        # For now, fetch payment status requires payment_ref
        # In production, this would be looked up from order_confirmed blob
        status = await workflow.fetch_payment_status(order_id=order_id, payment_ref="")
        
        return PaymentStatusResponse(
            order_id=order_id,
            payment_status=status.get("status", "UNKNOWN"),
            payment_ref=status.get("payment_ref"),
            amount_minor=status.get("amount_minor"),
            currency=status.get("currency"),
            updated_at=status.get("updated_at"),
        )
        
    except Exception as e:
        logger.error(f"Payment status fetch error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@orders_router.post(
    "/orders/{order_id}/cancel",
    response_model=CancelResponse,
    summary="Cancel a confirmed order",
)
async def cancel_order(
    order_id: str,
    request: CancelRequest,
    db: AsyncSession = Depends(get_db),
    redis: RedisCache = Depends(lambda: get_redis_cache()),
):
    """
    Cancel a confirmed order.
    
    **Path Parameters:**
    - `order_id`: Order ID to cancel
    
    **Request:**
    - `reason`: Cancellation reason (USER_CANCELLED, PAYMENT_FAILED, etc.)
    
    **Response:**
    - `status`: CANCELLED on success
    - `order_id`: Cancelled order ID
    
    **Note:**
    - Can only cancel orders in certain states (CONFIRMED, PENDING_PAYMENT, etc.)
    - Non-blocking: refunds/reversals are handled asynchronously
    """
    try:
        workflow = ConfirmationWorkflow(db, redis)
        
        result = await workflow.cancel_order(order_id, request.reason)
        
        return CancelResponse(
            status="CANCELLED",
            order_id=result.get("order_id"),
        )
        
    except Exception as e:
        logger.error(f"Cancel error: {e}", exc_info=True)
        return CancelResponse(
            status="FAILED",
            error_code="ICE_CANCEL_FAILED",
            error_message=str(e),
        )
