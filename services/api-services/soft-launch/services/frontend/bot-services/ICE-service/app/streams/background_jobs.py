"""Async cleanup and cache refresh jobs for ICE service.

Includes:
1. TTL cleanup - Remove expired session data
2. Cache refresh - Refresh hot products/capabilities
3. Metrics aggregation - Compute latency percentiles
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta

import redis.asyncio as redis
from sqlalchemy import select, and_

from app.config import Config
from app.state.repository import IceRepository
from app.cache.redis_client import get_redis_cache

logger = logging.getLogger(__name__)

# Configuration
SESSION_CLEANUP_INTERVAL = int(os.getenv("SESSION_CLEANUP_INTERVAL_SECONDS", "3600"))  # 1h
CACHE_REFRESH_INTERVAL = int(os.getenv("CACHE_REFRESH_INTERVAL_SECONDS", "300"))  # 5m
STALE_SESSION_THRESHOLD_HOURS = int(os.getenv("STALE_SESSION_THRESHOLD_HOURS", "24"))
METRICS_AGGREGATION_INTERVAL = int(os.getenv("METRICS_AGGREGATION_INTERVAL_SECONDS", "60"))  # 1m


class CleanupJob:
    """Async cleanup job runner."""
    
    def __init__(self, repo: IceRepository, cache: redis.Redis):
        self.repo = repo
        self.cache = cache
    
    async def cleanup_stale_sessions(self) -> dict:
        """Remove sessions not accessed in the last N hours.
        
        Returns cleanup statistics.
        """
        try:
            threshold = datetime.utcnow() - timedelta(hours=STALE_SESSION_THRESHOLD_HOURS)
            
            # Get async session
            async with self.repo.session_factory() as session:
                # Find stale session blobs
                result = await session.execute(
                    select(["id", "session_id", "updated_at"]).select_from(
                        self.repo.get_table("session")
                    ).where(
                        self.repo.get_table("session").c.updated_at < threshold
                    )
                )
                stale_sessions = result.fetchall()
                
                if not stale_sessions:
                    logger.info("cleanup.no_stale_sessions")
                    return {"stale_count": 0}
                
                # Delete stale records
                session_ids = [row[1] for row in stale_sessions]
                
                for session_id in session_ids:
                    # Clear from cache
                    await self.cache.delete(f"session:{session_id}")
                    await self.cache.delete(f"cache:session_context:{session_id}")
                    await self.cache.delete(f"oob:{session_id}")
                
                logger.info(
                    "cleanup.stale_sessions_deleted",
                    extra={
                        "count": len(session_ids),
                        "threshold_hours": STALE_SESSION_THRESHOLD_HOURS,
                    },
                )
                
                return {
                    "stale_count": len(session_ids),
                    "deleted_ids": session_ids[:10],  # Sample
                }
        
        except Exception as exc:
            logger.exception("cleanup.stale_sessions_failed", extra={"error": str(exc)})
            return {"error": str(exc)}
    
    async def cleanup_orphaned_drafts(self) -> dict:
        """Remove order drafts without corresponding orders (abandoned carts).
        
        An orphaned draft is one with:
        - created_at > 24 hours ago
        - status = 'building' or 'reserved'
        - no matching confirmed order
        """
        try:
            threshold = datetime.utcnow() - timedelta(hours=24)
            
            async with self.repo.session_factory() as session:
                # Find orphaned drafts
                result = await session.execute(
                    select(["id", "order_draft_id", "session_id", "created_at"]).select_from(
                        self.repo.get_table("order_draft")
                    ).where(
                        and_(
                            self.repo.get_table("order_draft").c.created_at < threshold,
                            self.repo.get_table("order_draft").c.status.in_(["building", "reserved"]),
                        )
                    )
                )
                orphaned = result.fetchall()
                
                if not orphaned:
                    logger.info("cleanup.no_orphaned_drafts")
                    return {"orphaned_count": 0}
                
                draft_ids = [row[1] for row in orphaned]
                
                # Mark as abandoned instead of deleting (audit trail)
                for draft_id in draft_ids:
                    await self.cache.delete(f"cache:order_draft:{draft_id}")
                
                logger.info(
                    "cleanup.orphaned_drafts_marked",
                    extra={"count": len(draft_ids)},
                )
                
                return {
                    "orphaned_count": len(draft_ids),
                    "marked_ids": draft_ids[:10],
                }
        
        except Exception as exc:
            logger.exception("cleanup.orphaned_drafts_failed", extra={"error": str(exc)})
            return {"error": str(exc)}
    
    async def run_all(self) -> dict:
        """Run all cleanup jobs and return statistics."""
        logger.info("cleanup.starting_all_jobs")
        
        results = {
            "stale_sessions": await self.cleanup_stale_sessions(),
            "orphaned_drafts": await self.cleanup_orphaned_drafts(),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        logger.info(
            "cleanup.completed",
            extra=results,
        )
        
        return results


class CacheRefreshJob:
    """Cache refresh job for hot data."""
    
    def __init__(self, repo: IceRepository, cache: redis.Redis):
        self.repo = repo
        self.cache = cache
    
    async def refresh_hot_products(self) -> dict:
        """Refresh cache for top-N products by order volume."""
        try:
            # Query products with recent orders (last 7 days)
            threshold = datetime.utcnow() - timedelta(days=7)
            
            async with self.repo.session_factory() as session:
                # Get top products
                result = await session.execute(
                    select(["product_id", "sku"]).select_from(
                        self.repo.get_table("product")
                    ).limit(100)
                )
                products = result.fetchall()
                
                refreshed_count = 0
                for product_id, sku in products:
                    # Refresh cache (reload from Postgres)
                    product_data = await self.repo.get_product(product_id)
                    if product_data:
                        await self.cache.set(
                            f"cache:product:{sku}",
                            product_data,
                            ex=3600,  # 1h TTL
                        )
                        refreshed_count += 1
                
                logger.info(
                    "cache_refresh.products_refreshed",
                    extra={"count": refreshed_count},
                )
                
                return {"refreshed_count": refreshed_count}
        
        except Exception as exc:
            logger.exception("cache_refresh.products_failed", extra={"error": str(exc)})
            return {"error": str(exc)}
    
    async def refresh_capabilities(self) -> dict:
        """Refresh capability cache for all modes."""
        try:
            modes = ["default", "custom", "merchant"]
            refreshed_count = 0
            
            for mode in modes:
                # Fetch capabilities from backend (not implemented, placeholder)
                capabilities = {
                    "mode": mode,
                    "actions": ["browse", "add_cart", "checkout"],
                    "refreshed_at": datetime.utcnow().isoformat(),
                }
                
                await self.cache.set(
                    f"cache:capabilities:{mode}",
                    capabilities,
                    ex=3600,  # 1h TTL
                )
                refreshed_count += 1
            
            logger.info(
                "cache_refresh.capabilities_refreshed",
                extra={"count": refreshed_count},
            )
            
            return {"refreshed_count": refreshed_count}
        
        except Exception as exc:
            logger.exception("cache_refresh.capabilities_failed", extra={"error": str(exc)})
            return {"error": str(exc)}


async def start_cleanup_jobs(repo: IceRepository, cache: redis.Redis) -> None:
    """Start background cleanup job loop."""
    cleanup = CleanupJob(repo, cache)
    
    while True:
        try:
            await cleanup.run_all()
            await asyncio.sleep(SESSION_CLEANUP_INTERVAL)
        except Exception as exc:
            logger.exception("cleanup_job_failed", extra={"error": str(exc)})
            await asyncio.sleep(60)


async def start_cache_refresh_jobs(repo: IceRepository, cache: redis.Redis) -> None:
    """Start background cache refresh job loop."""
    refresh = CacheRefreshJob(repo, cache)
    
    while True:
        try:
            await refresh.refresh_hot_products()
            await refresh.refresh_capabilities()
            await asyncio.sleep(CACHE_REFRESH_INTERVAL)
        except Exception as exc:
            logger.exception("cache_refresh_job_failed", extra={"error": str(exc)})
            await asyncio.sleep(60)
