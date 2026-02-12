"""Repository layer for ICE state persistence."""

import logging
import os
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update

from app.state.models import (
    IceSession,
    IceOrderDraft,
    IceProductSnapshot,
    IceCatalogSnapshot,
    IceAffiliateContext,
    IceAuditLog,
    IceIdempotencyCache,
    IceMessageLog,
)
from app.config import Config
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)


# Database Engine Setup
_schema = os.getenv("PG_SCHEMA", "").strip()
_server_settings = {"application_name": "ice-service"}
if _schema:
    _server_settings["search_path"] = _schema

engine = create_async_engine(
    Config.DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    connect_args={"server_settings": _server_settings},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db():
    """Get database session dependency for FastAPI."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


class IceRepository:
    """Repository for ICE persistence operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # Session Operations
    
    async def create_session(self, session_id: str, phone_number: str, business_id: str, blob: Dict[str, Any]) -> IceSession:
        """Create new session record."""
        session = IceSession(
            session_id=session_id,
            phone_number=phone_number,
            business_id=business_id,
            blob=blob,
            schema_version="1.0",
        )
        self.db.add(session)
        await self.db.flush()
        logger.info(f"Created session: {session_id}")
        return session
    
    async def get_session(self, session_id: str) -> Optional[IceSession]:
        """Retrieve session by ID."""
        query = select(IceSession).where(IceSession.session_id == session_id)
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def update_session(self, session_id: str, blob: Dict[str, Any]) -> bool:
        """Update session blob."""
        query = update(IceSession).where(IceSession.session_id == session_id).values(blob=blob, updated_at=datetime.now(timezone.utc))
        result = await self.db.execute(query)
        await self.db.flush()
        logger.debug(f"Updated session: {session_id}")
        return result.rowcount > 0
    
    # Order Draft Operations
    
    async def create_order_draft(self, session_id: str, blob: Dict[str, Any], idempotency_key: Optional[str] = None) -> IceOrderDraft:
        """Create new order draft."""
        draft = IceOrderDraft(
            session_id=session_id,
            blob=blob,
            status="draft",
            schema_version="1.0",
            idempotency_key=idempotency_key,
        )
        self.db.add(draft)
        await self.db.flush()
        logger.info(f"Created order draft for session: {session_id}")
        return draft
    
    async def get_order_draft(self, session_id: str) -> Optional[IceOrderDraft]:
        """Retrieve latest order draft for session."""
        query = select(IceOrderDraft).where(IceOrderDraft.session_id == session_id).order_by(IceOrderDraft.created_at.desc())
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def update_order_draft(self, session_id: str, blob: Dict[str, Any], status: str = "draft") -> bool:
        """Update order draft."""
        query = update(IceOrderDraft).where(IceOrderDraft.session_id == session_id).values(
            blob=blob,
            status=status,
            updated_at=datetime.now(timezone.utc),
        )
        result = await self.db.execute(query)
        await self.db.flush()
        logger.debug(f"Updated order draft for session: {session_id}, status: {status}")
        return result.rowcount > 0
    
    # Catalog Snapshot Operations
    
    async def save_catalog_snapshot(self, business_id: str, blob: Dict[str, Any]) -> IceCatalogSnapshot:
        """Save or update catalog snapshot."""
        existing = await self.db.execute(select(IceCatalogSnapshot).where(IceCatalogSnapshot.business_id == business_id))
        catalog = existing.scalars().first()
        
        if catalog:
            catalog.blob = blob
            catalog.updated_at = datetime.now(timezone.utc)
        else:
            catalog = IceCatalogSnapshot(
                business_id=business_id,
                blob=blob,
                schema_version="1.0",
            )
            self.db.add(catalog)
        
        await self.db.flush()
        logger.info(f"Saved catalog snapshot for business: {business_id}")
        return catalog
    
    async def get_catalog_snapshot(self, business_id: str) -> Optional[IceCatalogSnapshot]:
        """Retrieve catalog snapshot."""
        query = select(IceCatalogSnapshot).where(IceCatalogSnapshot.business_id == business_id)
        result = await self.db.execute(query)
        return result.scalars().first()

    # Product Snapshot Operations

    async def save_product_snapshot(self, business_id: str, product_id: str, blob: Dict[str, Any], variant_id: Optional[str] = None) -> IceProductSnapshot:
        """Save or update a product snapshot."""
        existing = await self.db.execute(
            select(IceProductSnapshot).where(
                IceProductSnapshot.business_id == business_id,
                IceProductSnapshot.product_id == product_id,
                IceProductSnapshot.variant_id == variant_id,
            )
        )
        snapshot = existing.scalars().first()

        if snapshot:
            snapshot.blob = blob
            snapshot.updated_at = datetime.now(timezone.utc)
        else:
            snapshot = IceProductSnapshot(
                business_id=business_id,
                product_id=product_id,
                variant_id=variant_id,
                blob=blob,
                schema_version="1.0",
            )
            self.db.add(snapshot)

        await self.db.flush()
        logger.info(f"Saved product snapshot for business: {business_id}, product: {product_id}")
        return snapshot

    async def get_product_snapshot(self, business_id: str, product_id: str, variant_id: Optional[str] = None) -> Optional[IceProductSnapshot]:
        """Retrieve product snapshot by business/product/variant."""
        query = select(IceProductSnapshot).where(
            IceProductSnapshot.business_id == business_id,
            IceProductSnapshot.product_id == product_id,
            IceProductSnapshot.variant_id == variant_id,
        )
        result = await self.db.execute(query)
        return result.scalars().first()
    
    # Affiliate Context Operations
    
    async def create_affiliate_context(self, session_id: str, blob: Dict[str, Any]) -> IceAffiliateContext:
        """Create new affiliate context."""
        ctx = IceAffiliateContext(
            session_id=session_id,
            blob=blob,
            status="pending",
            schema_version="1.0",
        )
        self.db.add(ctx)
        await self.db.flush()
        logger.info(f"Created affiliate context for session: {session_id}")
        return ctx
    
    async def update_affiliate_context(self, session_id: str, order_id: str, affiliate_id: str, blob: Dict[str, Any], status: str = "pending") -> bool:
        """Update affiliate context."""
        query = update(IceAffiliateContext).where(
            IceAffiliateContext.session_id == session_id
        ).values(
            order_id=order_id,
            affiliate_id=affiliate_id,
            blob=blob,
            status=status,
            updated_at=datetime.now(timezone.utc),
        )
        result = await self.db.execute(query)
        await self.db.flush()
        logger.debug(f"Updated affiliate context for session: {session_id}, status: {status}")
        return result.rowcount > 0
    
    # Audit Log Operations
    
    async def log_event(
        self,
        session_id: str,
        event_type: str,
        event_payload: Dict[str, Any],
        order_id: Optional[str] = None,
        business_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> IceAuditLog:
        """Create audit log entry."""
        log = IceAuditLog(
            session_id=session_id,
            order_id=order_id,
            business_id=business_id,
            event_type=event_type,
            event_payload=event_payload,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
        self.db.add(log)
        await self.db.flush()
        logger.debug(f"Logged event: {event_type} for session: {session_id}")
        return log
    
    # Idempotency Cache Operations
    
    async def get_idempotency_response(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Get cached response for idempotency key."""
        query = select(IceIdempotencyCache).where(IceIdempotencyCache.idempotency_key == idempotency_key)
        result = await self.db.execute(query)
        cache = result.scalars().first()
        
        if cache:
            logger.debug(f"Idempotency cache hit: {idempotency_key}")
            return {
                "status": cache.response_status,
                "body": cache.response_body,
            }
        return None

    # Message Log Operations

    async def get_message_log_by_correlation(self, correlation_id: str) -> Optional[IceMessageLog]:
        query = select(IceMessageLog).where(IceMessageLog.correlation_id == correlation_id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def upsert_message_log(
        self,
        *,
        correlation_id: Optional[str],
        session_id: str,
        business_id: Optional[str],
        user_phone: Optional[str],
        bot_phone: Optional[str],
        incoming_message: Optional[str],
        incoming_payload: Optional[Dict[str, Any]],
        incoming_at: Optional[datetime],
        outgoing_message: Optional[str],
        outgoing_payload: Optional[Dict[str, Any]],
        outgoing_status: Optional[str],
        outgoing_at: Optional[datetime],
        provider_message_id: Optional[str],
        error_message: Optional[str],
    ) -> IceMessageLog:
        log = None
        if correlation_id:
            log = await self.get_message_log_by_correlation(correlation_id)

        if log:
            log.session_id = session_id
            log.business_id = business_id
            log.user_phone = user_phone
            log.bot_phone = bot_phone
            log.incoming_message = incoming_message or log.incoming_message
            log.incoming_payload = incoming_payload or log.incoming_payload
            log.incoming_at = incoming_at or log.incoming_at
            log.outgoing_message = outgoing_message or log.outgoing_message
            log.outgoing_payload = outgoing_payload or log.outgoing_payload
            log.outgoing_status = outgoing_status or log.outgoing_status
            log.outgoing_at = outgoing_at or log.outgoing_at
            log.provider_message_id = provider_message_id or log.provider_message_id
            log.error_message = error_message or log.error_message
            log.updated_at = datetime.now(timezone.utc)
        else:
            log = IceMessageLog(
                correlation_id=correlation_id,
                session_id=session_id,
                business_id=business_id,
                user_phone=user_phone,
                bot_phone=bot_phone,
                incoming_message=incoming_message,
                incoming_payload=incoming_payload,
                incoming_at=incoming_at,
                outgoing_message=outgoing_message,
                outgoing_payload=outgoing_payload,
                outgoing_status=outgoing_status,
                outgoing_at=outgoing_at,
                provider_message_id=provider_message_id,
                error_message=error_message,
            )
            self.db.add(log)

        await self.db.flush()
        return log
    
    async def cache_response(
        self,
        idempotency_key: str,
        request_method: str,
        request_path: str,
        response_status: str,
        response_body: Dict[str, Any],
        ttl_hours: int = 24,
    ) -> bool:
        """Cache response for idempotency."""
        from datetime import timedelta
        
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        
        cache = IceIdempotencyCache(
            idempotency_key=idempotency_key,
            request_method=request_method,
            request_path=request_path,
            response_status=response_status,
            response_body=response_body,
            expires_at=expires_at,
        )
        self.db.add(cache)
        await self.db.flush()
        logger.debug(f"Cached response for idempotency key: {idempotency_key}")
        return True
    
    async def commit(self) -> None:
        """Commit transaction."""
        await self.db.commit()
    
    async def rollback(self) -> None:
        """Rollback transaction."""
        await self.db.rollback()
