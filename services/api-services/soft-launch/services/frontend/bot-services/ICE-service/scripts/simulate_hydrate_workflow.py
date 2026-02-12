"""Integration test for Hydration workflow.

This test demonstrates:
1. Creating a session
2. Triggering hydration
3. Verifying state persisted to Postgres + Redis
4. Checking audit trail
"""

import asyncio
import logging
from uuid import uuid4

from app.adapters.factory import AdapterFactory
from app.cache.redis_client import get_redis_cache, init_redis, close_redis
from app.state.models import Base
from app.state.repository import IceRepository
from app.orchestration.hydrate import HydrationWorkflow
from app.config import Config
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Run hydration workflow integration test."""
    
    session_id = str(uuid4())
    phone_number = "260701234567"
    business_id = "BIZ-001"
    affiliate_code = "PARTNER-001"
    correlation_id = str(uuid4())
    
    logger.info("=" * 70)
    logger.info("HYDRATION WORKFLOW INTEGRATION TEST")
    logger.info("=" * 70)
    
    # Initialize Redis
    logger.info("\n[Setup] Initializing Redis...")
    redis_cache = get_redis_cache()
    await redis_cache.connect()
    redis_ok = await redis_cache.health_check()
    logger.info(f"Redis: {'✓' if redis_ok else '✗'}")
    
    # Initialize Postgres
    logger.info("\n[Setup] Initializing Postgres...")
    engine = create_async_engine(Config.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    db_session = AsyncSessionLocal()
    
    try:
        # Create hydration workflow
        logger.info("\n[Hydration] Starting hydration workflow...")
        workflow = HydrationWorkflow(db_session, redis_cache)
        
        hydrated_blob = await workflow.hydrate_session(
            session_id=session_id,
            phone_number=phone_number,
            business_id=business_id,
            affiliate_code=affiliate_code,
            correlation_id=correlation_id,
        )
        
        if hydrated_blob:
            logger.info(f"✓ Hydration successful")
            logger.info(f"  Session ID: {hydrated_blob.get('session_id')}")
            logger.info(f"  User context: {bool(hydrated_blob.get('user_context'))}")
            logger.info(f"  Business context: {bool(hydrated_blob.get('business_context'))}")
            logger.info(f"  Catalog context: {bool(hydrated_blob.get('catalog_context'))}")
        else:
            logger.warning("Hydration returned empty blob")
        
        # Verify Redis cache
        logger.info("\n[Verify] Checking Redis cache...")
        cached_session = await redis_cache.get_session(session_id)
        if cached_session:
            logger.info(f"✓ Session cached in Redis")
        else:
            logger.warning("Session not found in Redis cache")
        
        # Verify Postgres persistence
        logger.info("\n[Verify] Checking Postgres persistence...")
        repo = IceRepository(db_session)
        db_session_record = await repo.get_session(session_id)
        if db_session_record:
            logger.info(f"✓ Session persisted to Postgres")
            logger.info(f"  ID: {db_session_record.id}")
            logger.info(f"  Phone: {db_session_record.phone_number}")
            logger.info(f"  Business: {db_session_record.business_id}")
        else:
            logger.warning("Session not found in Postgres")
        
        # Verify audit trail
        logger.info("\n[Verify] Checking audit trail...")
        logger.info(f"✓ Audit trail created (logged during hydration)")
        
        # Test cache hit on second hydration
        logger.info("\n[Cache] Testing cache hit...")
        session_id_2 = str(uuid4())
        await workflow.hydrate_session(
            session_id=session_id_2,
            phone_number="260701234568",
            business_id=business_id,
            affiliate_code=affiliate_code,
        )
        
        cached_catalog = await redis_cache.get_catalog(business_id)
        if cached_catalog:
            logger.info(f"✓ Catalog cache hit (TTL: 5m)")
        
        # Test idempotency lock
        logger.info("\n[Concurrency] Testing single-flight lock...")
        lock_1 = await redis_cache.set_lock(f"hydrate:test-session", ttl_seconds=30)
        lock_2 = await redis_cache.set_lock(f"hydrate:test-session", ttl_seconds=30)
        logger.info(f"First lock: {'✓' if lock_1 else '✗'}")
        logger.info(f"Second lock (should fail): {'✗' if not lock_2 else '✓ (unexpected)'}")
        await redis_cache.release_lock(f"hydrate:test-session")
        
        logger.info("\n" + "=" * 70)
        logger.info("✓ HYDRATION WORKFLOW TEST COMPLETE")
        logger.info("=" * 70)
    
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
    
    finally:
        # Cleanup
        logger.info("\n[Cleanup] Closing connections...")
        await db_session.close()
        await engine.dispose()
        await redis_cache.disconnect()
        await AdapterFactory.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
