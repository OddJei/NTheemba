"""FastAPI request/response schemas for ICE service endpoints."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# Hydration Schemas
# ============================================================================

class HydrateSessionRequest(BaseModel):
    """Request to hydrate session context."""
    event_id: str = Field(..., description="Unique event ID for idempotency")
    session_id: str = Field(..., description="Session ID to hydrate")
    user_id: Optional[str] = Field(None, description="User ID (optional)")
    user_phone: Optional[str] = Field(None, description="User phone number (optional)")
    from_number: Optional[str] = Field(None, description="Inbound customer phone number (optional)")
    to_number: Optional[str] = Field(None, description="Business phone number (optional)")
    bot_id: Optional[str] = Field(None, description="Bot ID (optional)")
    business_id: Optional[str] = Field(None, description="Business ID (optional)")
    platform: Optional[str] = Field("WHATSAPP", description="Platform (WHATSAPP, SMS, etc.)")
    bot_type: Optional[str] = Field("MSME", description="Bot type (MSME, PAYMENT, etc.)")
    reason: Optional[str] = Field(None, description="Reason for hydration (cache_miss, stale, etc.)")
    required_blobs: Optional[List[str]] = Field(
        default=["session", "order_draft", "bot_meta"],
        description="List of blob types to hydrate"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "evt_20251226_0001",
                "session_id": "sess_abc123",
                "user_id": "user_789",
                "bot_id": "bot_456",
                "reason": "ingress_cache_miss",
                "required_blobs": ["session", "order_draft", "bot_meta"]
            }
        }


class HydrateSessionResponse(BaseModel):
    """Response with hydrated session context."""
    hydrated: bool
    session_blob: Optional[Dict[str, Any]] = None
    order_draft_blob: Optional[Dict[str, Any]] = None
    bot_meta_blob: Optional[Dict[str, Any]] = None
    user_blob: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "hydrated": True,
                "session_blob": {
                    "session_id": "sess_abc123",
                    "user_id": "user_789",
                    "bot_id": "bot_456",
                    "bot_type": "custom",
                    "current_node": "inspect_cart_item",
                    "expected_input": "confirmation",
                    "schema_version": "1.0",
                    "hydrated_at": "2025-12-26T09:12:00Z"
                },
                "order_draft_blob": {
                    "order_id": "tmp_ord_987",
                    "items": [{"product_id": "p_123", "quantity": 2, "price_snapshot": 120.0}],
                    "schema_version": "1.0",
                    "hydrated_at": "2025-12-26T09:12:00Z"
                }
            }
        }


# ============================================================================
# Message Log Schemas
# ============================================================================

class MessageLogRequest(BaseModel):
    """Upsert incoming/outgoing message pair for a session."""
    correlation_id: Optional[str] = Field(None, description="Correlation ID for pairing in/out messages")
    session_id: str = Field(..., description="Session ID")
    business_id: Optional[str] = Field(None, description="Business ID")
    user_phone: Optional[str] = Field(None, description="User phone")
    bot_phone: Optional[str] = Field(None, description="Bot phone")

    incoming_message: Optional[str] = Field(None, description="Incoming message text")
    incoming_payload: Optional[Dict[str, Any]] = Field(None, description="Raw incoming payload")
    incoming_at: Optional[str] = Field(None, description="Incoming timestamp (ISO)")

    outgoing_message: Optional[str] = Field(None, description="Outgoing message text")
    outgoing_payload: Optional[Dict[str, Any]] = Field(None, description="Raw outgoing payload")
    outgoing_status: Optional[str] = Field(None, description="pending | sent | failed")
    outgoing_at: Optional[str] = Field(None, description="Outgoing timestamp (ISO)")
    provider_message_id: Optional[str] = Field(None, description="Provider message id")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class MessageLogResponse(BaseModel):
    """Response for message log upsert."""
    id: str
    correlation_id: Optional[str]
    session_id: str
    status: Optional[str]


# ============================================================================
# Reserve Schemas
# ============================================================================

class ReserveRequest(BaseModel):
    """Request to reserve inventory."""
    session_id: str = Field(..., description="Session ID")
    cart_id: str = Field(..., description="Cart ID")
    user_id: str = Field(..., description="User ID")
    business_id: str = Field(..., description="Business ID")
    payment_method: str = Field(default="mobile_money", description="Payment method")
    payment_number: Optional[str] = Field(None, description="Payment number (phone for mobile money)")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key for duplicate prevention")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "sess_abc123",
                "cart_id": "cart_xyz789",
                "user_id": "user_456",
                "business_id": "biz_321",
                "payment_method": "mobile_money",
                "payment_number": "260970000001",
                "idempotency_key": "evt_20251226_0002"
            }
        }


class ReserveResponse(BaseModel):
    """Response from reserve operation."""
    status: str = Field(..., description="RESERVED or error status")
    order_draft_id: Optional[str] = None
    reservation_ref: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "status": "RESERVED",
                "order_draft_id": "draft_abc123",
                "reservation_ref": "res_20251226_0001"
            }
        }


# ============================================================================
# Confirm Schemas
# ============================================================================

class ConfirmRequest(BaseModel):
    """Request to confirm order."""
    order_draft_id: str = Field(..., description="Order draft ID from reserve")
    payment_details: Dict[str, Any] = Field(..., description="Payment details")
    delivery_details: Optional[Dict[str, Any]] = Field(None, description="Delivery details")
    affiliate_context: Optional[Dict[str, Any]] = Field(None, description="Affiliate context")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key")

    class Config:
        json_schema_extra = {
            "example": {
                "order_draft_id": "draft_abc123",
                "payment_details": {
                    "method": "mobile_money",
                    "phone_number": "260970000001",
                    "amount_minor": 50000,
                    "currency": "ZMW"
                },
                "delivery_details": {
                    "method": "standard",
                    "address": "123 Main St, Kitwe"
                },
                "affiliate_context": {
                    "affiliate_id": "aff_123",
                    "affiliate_code": "ACODE123"
                },
                "idempotency_key": "evt_20251226_0003"
            }
        }


class ConfirmResponse(BaseModel):
    """Response from confirm operation."""
    status: str = Field(..., description="CONFIRMED or error status")
    order_id: Optional[str] = None
    payment_ref: Optional[str] = None
    delivery_id: Optional[str] = None
    delivery_code: Optional[str] = None
    attribution_success: Optional[bool] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "status": "CONFIRMED",
                "order_id": "ord_20251226_0001",
                "payment_ref": "pay_xyz789",
                "delivery_id": "deliv_abc123",
                "delivery_code": "DEL2025000001",
                "attribution_success": True
            }
        }


# ============================================================================
# Payment Status Schemas
# ============================================================================

class PaymentStatusResponse(BaseModel):
    """Response with payment status."""
    order_id: str
    payment_status: str = Field(..., description="PENDING, COMPLETED, FAILED, etc.")
    payment_ref: Optional[str] = None
    amount_minor: Optional[int] = None
    currency: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "order_id": "ord_20251226_0001",
                "payment_status": "COMPLETED",
                "payment_ref": "pay_xyz789",
                "amount_minor": 50000,
                "currency": "ZMW",
                "updated_at": "2025-12-26T09:15:00Z"
            }
        }


# ============================================================================
# Cancel Schemas
# ============================================================================

class CancelRequest(BaseModel):
    """Request to cancel order."""
    reason: str = Field(..., description="Cancellation reason")

    class Config:
        json_schema_extra = {
            "example": {
                "reason": "USER_CANCELLED"
            }
        }


class CancelResponse(BaseModel):
    """Response from cancel operation."""
    status: str = Field(..., description="CANCELLED or error status")
    order_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "status": "CANCELLED",
                "order_id": "ord_20251226_0001"
            }
        }


# ============================================================================
# Health Check Schemas
# ============================================================================

class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str
    redis: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "status": "ok",
                "redis": {
                    "connected": True,
                    "latency_ms": 1.23
                }
            }
        }


class ReadinessCheckResponse(BaseModel):
    """Readiness check response."""
    status: str

    class Config:
        json_schema_extra = {
            "example": {
                "status": "ready"
            }
        }
