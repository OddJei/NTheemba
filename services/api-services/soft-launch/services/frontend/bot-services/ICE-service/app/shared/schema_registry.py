"""Schema registry for ICE JSONB blobs."""

from typing import Dict, Any, Optional
from datetime import datetime


SCHEMA_REGISTRY: Dict[str, str] = {
    "session": "v1",
    "oob": "v2",
    "order_draft": "v1",
    "product": "v1",
    "catalog": "v1",
    "affiliate_ctx": "v1",
}


def get_schema_version(blob_type: str) -> str:
    return SCHEMA_REGISTRY.get(blob_type, "v1")


def create_session_blob(
    session_id: str,
    user_id: str,
    phone_number: str,
    business_id: str,
    user_context: Optional[Dict[str, Any]] = None,
    business_context: Optional[Dict[str, Any]] = None,
    catalog_context: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a session blob conforming to the session schema contract.
    
    Args:
        session_id: Unique session identifier
        user_id: User identifier (or "N/A" if not authenticated)
        phone_number: User phone number
        business_id: Business identifier
        user_context: User-specific context from MSME
        business_context: Business-specific context from MSME
        catalog_context: Catalog snapshot from Catalog/Inventory
        metadata: Additional metadata
    
    Returns:
        Session blob conforming to contract schema
    """
    return {
        "session_id": session_id,
        "user_id": user_id,
        "user_phone": phone_number,
        "bot_id": metadata.get("bot_id", "default") if metadata else "default",
        "platform": metadata.get("platform", "WHATSAPP") if metadata else "WHATSAPP",
        "bot_type": metadata.get("bot_type", "MSME") if metadata else "MSME",
        "business_id": business_id,
        "session_start": datetime.utcnow().isoformat(),
        "last_activity": datetime.utcnow().isoformat(),
        "session_state": {
            "current_node": "welcome",
            "breadcrumbs": [],
            "context_vars": {}
        },
        "interaction_count": 0,
        "events": [],
        "user_context": user_context or {},
        "business_context": business_context or {},
        "catalog_context": catalog_context or {},
        "metadata": metadata or {},
    }


def create_order_draft_blob(
    order_draft_id: str,
    session_id: str,
    business_id: str,
    cart_items: list,
    cart_total_minor: int,
    cart_currency: str = "ZMW",
    payment_method: Optional[str] = None,
    delivery_method: Optional[str] = None,
    status: str = "DRAFT",
) -> Dict[str, Any]:
    """
    Create an order draft blob conforming to the order_draft schema contract.
    
    Args:
        order_draft_id: Unique order draft identifier
        session_id: Associated session identifier
        business_id: Business identifier
        cart_items: List of cart items
        cart_total_minor: Total cart value in minor units
        cart_currency: Currency code (default: ZMW)
        payment_method: Payment method (MOBILE_MONEY, CARD, COD, BANK_TRANSFER)
        delivery_method: Delivery method (DELIVERY, PICKUP, COURIER)
        status: Order status (DRAFT, RESERVED, CONFIRMED, CANCELLED)
    
    Returns:
        Order draft blob conforming to contract schema
    """
    return {
        "order_draft_id": order_draft_id,
        "session_id": session_id,
        "business_id": business_id,
        "cart_items": cart_items,
        "cart_total_minor": cart_total_minor,
        "cart_currency": cart_currency,
        "payment_method": payment_method,
        "delivery_method": delivery_method,
        "status": status,
        "created_at": datetime.utcnow().isoformat(),
        "reserved_until": None,
        "reserved_ref": None,
    }


def create_bot_meta_blob(
    session_id: str,
    bot_instance_id: str,
    engine_version: str = "1.0.0",
    last_intent: Optional[Dict[str, Any]] = None,
    slots: Optional[Dict[str, Any]] = None,
    session_flags: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a bot meta blob conforming to the bot_meta schema contract.
    
    Args:
        session_id: Associated session identifier
        bot_instance_id: Bot instance identifier
        engine_version: Bot engine version
        last_intent: Last detected intent with confidence and entities
        slots: Conversation slots
        session_flags: Session-level flags
    
    Returns:
        Bot meta blob conforming to contract schema
    """
    return {
        "session_id": session_id,
        "bot_instance_id": bot_instance_id,
        "engine_version": engine_version,
        "last_intent": last_intent,
        "slots": slots or {},
        "session_flags": session_flags or {
            "is_returning_user": False,
            "has_active_order": False,
            "language": "en"
        },
    }


def create_order_confirmed_blob(
    session_id: str,
    order_id: str,
    order_draft_id: str,
    user_id: str,
    business_id: str,
    items: list,
    total_amount_minor: int,
    payment_method: str,
    payment_number: str,
    payment_ref: Optional[str] = None,
    delivery_id: Optional[str] = None,
    delivery_code: Optional[str] = None,
    pickup_location: Optional[Dict[str, Any]] = None,
    delivery_location: Optional[Dict[str, Any]] = None,
    status: str = "CONFIRMED",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create an order confirmed blob for persisting confirmed orders.

    Args:
        session_id: Associated session identifier
        order_id: Unique order identifier from Cart/Order service
        order_draft_id: Original order draft identifier
        user_id: User identifier
        business_id: Business identifier
        items: List of order items
        total_amount_minor: Total order amount in minor units
        payment_method: Payment method used
        payment_number: Payment phone number or account
        payment_ref: Payment reference from payment initiation
        delivery_id: Delivery task identifier
        delivery_code: Delivery tracking code
        pickup_location: Pickup location details
        delivery_location: Delivery destination details
        status: Order status (CONFIRMED, PAID, CANCELLED)
        metadata: Additional metadata

    Returns:
        Order confirmed blob
    """
    return {
        "session_id": session_id,
        "order_id": order_id,
        "order_draft_id": order_draft_id,
        "user_id": user_id,
        "business_id": business_id,
        "items": items,
        "total_amount_minor": total_amount_minor,
        "payment_method": payment_method,
        "payment_number": payment_number,
        "payment_ref": payment_ref,
        "delivery_id": delivery_id,
        "delivery_code": delivery_code,
        "pickup_location": pickup_location,
        "delivery_location": delivery_location,
        "status": status,
        "confirmed_at": datetime.utcnow().isoformat(),
        "metadata": metadata or {},
    }


def create_delivery_task_blob(
    order_id: str,
    delivery_id: str,
    delivery_code: Optional[str] = None,
    pickup_location: Optional[Dict[str, Any]] = None,
    delivery_location: Optional[Dict[str, Any]] = None,
    recipient_phone: Optional[str] = None,
    status: str = "INITIATED",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a delivery task blob for persisting delivery tasks.

    Args:
        order_id: Associated order identifier
        delivery_id: Unique delivery task identifier from Delivery service
        delivery_code: Delivery tracking code
        pickup_location: Pickup location details
        delivery_location: Delivery destination details
        recipient_phone: Recipient phone number
        status: Delivery status (INITIATED, IN_TRANSIT, DELIVERED, CANCELLED)
        metadata: Additional metadata

    Returns:
        Delivery task blob
    """
    return {
        "order_id": order_id,
        "delivery_id": delivery_id,
        "delivery_code": delivery_code,
        "pickup_location": pickup_location,
        "delivery_location": delivery_location,
        "recipient_phone": recipient_phone,
        "status": status,
        "created_at": datetime.utcnow().isoformat(),
        "metadata": metadata or {},
    }
