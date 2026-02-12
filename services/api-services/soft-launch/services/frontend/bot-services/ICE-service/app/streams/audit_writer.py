"""oob:audit writer - Append-only audit trail for Order Object mutations.

Publishes all OOB state changes to 'oob:audit' stream for replay, audit, and compliance.
"""

import asyncio
import json
import logging
import os
from typing import Any, Optional
from datetime import datetime

import redis.asyncio as redis

from app.config import Config

logger = logging.getLogger(__name__)

AUDIT_STREAM = os.getenv("OOB_AUDIT_STREAM", "oob:audit")
AUDIT_RETENTION_DAYS = int(os.getenv("OOB_AUDIT_RETENTION_DAYS", "30"))


class AuditWriter:
    """Write-only client for OOB audit trail."""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
    
    async def log_hydration(
        self,
        event_id: str,
        session_id: str,
        blobs_hydrated: dict[str, str],
        adapter_metrics: dict[str, float],
        correlation_id: Optional[str] = None,
    ) -> str:
        """Log session hydration event."""
        entry_id = await self.redis.xadd(
            AUDIT_STREAM,
            {
                "event_type": "session_hydrated",
                "event_id": event_id,
                "session_id": session_id,
                "correlation_id": correlation_id or event_id,
                "timestamp": datetime.utcnow().isoformat(),
                "payload": json.dumps({
                    "blobs_hydrated": list(blobs_hydrated.keys()),
                    "adapter_metrics": adapter_metrics,
                }),
            },
        )
        logger.info(
            "audit.session_hydrated",
            extra={
                "entry_id": entry_id,
                "event_id": event_id,
                "session_id": session_id,
                "blobs_count": len(blobs_hydrated),
            },
        )
        return entry_id
    
    async def log_reserve(
        self,
        event_id: str,
        session_id: str,
        order_draft_id: str,
        reservation_ref: str,
        cart_items: list[dict],
        status: str,
        error_code: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        """Log inventory reservation event."""
        entry_id = await self.redis.xadd(
            AUDIT_STREAM,
            {
                "event_type": "inventory_reserved",
                "event_id": event_id,
                "session_id": session_id,
                "order_draft_id": order_draft_id,
                "correlation_id": correlation_id or event_id,
                "timestamp": datetime.utcnow().isoformat(),
                "status": status,
                "payload": json.dumps({
                    "reservation_ref": reservation_ref,
                    "cart_items_count": len(cart_items),
                    "error_code": error_code,
                }),
            },
        )
        logger.info(
            "audit.inventory_reserved",
            extra={
                "entry_id": entry_id,
                "event_id": event_id,
                "reservation_ref": reservation_ref,
                "status": status,
            },
        )
        return entry_id
    
    async def log_confirm(
        self,
        event_id: str,
        session_id: str,
        order_id: str,
        payment_ref: str,
        delivery_id: str,
        attribution_success: bool,
        status: str,
        error_code: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        """Log order confirmation event."""
        entry_id = await self.redis.xadd(
            AUDIT_STREAM,
            {
                "event_type": "order_confirmed",
                "event_id": event_id,
                "session_id": session_id,
                "order_id": order_id,
                "correlation_id": correlation_id or event_id,
                "timestamp": datetime.utcnow().isoformat(),
                "status": status,
                "payload": json.dumps({
                    "payment_ref": payment_ref,
                    "delivery_id": delivery_id,
                    "attribution_success": attribution_success,
                    "error_code": error_code,
                }),
            },
        )
        logger.info(
            "audit.order_confirmed",
            extra={
                "entry_id": entry_id,
                "event_id": event_id,
                "order_id": order_id,
                "status": status,
            },
        )
        return entry_id
    
    async def log_payment_status(
        self,
        event_id: str,
        session_id: str,
        order_id: str,
        payment_ref: str,
        payment_status: str,
        amount_minor: int,
        currency: str,
        correlation_id: Optional[str] = None,
    ) -> str:
        """Log payment status fetch event."""
        entry_id = await self.redis.xadd(
            AUDIT_STREAM,
            {
                "event_type": "payment_status_fetched",
                "event_id": event_id,
                "session_id": session_id,
                "order_id": order_id,
                "correlation_id": correlation_id or event_id,
                "timestamp": datetime.utcnow().isoformat(),
                "payment_status": payment_status,
                "payload": json.dumps({
                    "payment_ref": payment_ref,
                    "amount_minor": amount_minor,
                    "currency": currency,
                }),
            },
        )
        logger.info(
            "audit.payment_status_fetched",
            extra={
                "entry_id": entry_id,
                "event_id": event_id,
                "payment_status": payment_status,
            },
        )
        return entry_id
    
    async def log_cancel(
        self,
        event_id: str,
        session_id: str,
        order_id: str,
        reason: str,
        status: str,
        error_code: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        """Log order cancellation event."""
        entry_id = await self.redis.xadd(
            AUDIT_STREAM,
            {
                "event_type": "order_cancelled",
                "event_id": event_id,
                "session_id": session_id,
                "order_id": order_id,
                "correlation_id": correlation_id or event_id,
                "timestamp": datetime.utcnow().isoformat(),
                "status": status,
                "reason": reason,
                "payload": json.dumps({
                    "error_code": error_code,
                }),
            },
        )
        logger.info(
            "audit.order_cancelled",
            extra={
                "entry_id": entry_id,
                "event_id": event_id,
                "order_id": order_id,
                "reason": reason,
            },
        )
        return entry_id


def get_audit_writer(redis_client: redis.Redis) -> AuditWriter:
    """Get a singleton AuditWriter instance."""
    return AuditWriter(redis_client)
