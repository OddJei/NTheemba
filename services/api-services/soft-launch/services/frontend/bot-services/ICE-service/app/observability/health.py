"""
Phase 6: Observability - Health Checks & Readiness

Implement liveness (health) and readiness probes for Kubernetes/container orchestration.
"""

from __future__ import annotations

from typing import Any
from dataclasses import dataclass
from enum import Enum

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


class HealthStatus(str, Enum):
    """Health status enum."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    status: HealthStatus
    components: dict[str, Any]
    timestamp: str | None = None

    def is_ready(self) -> bool:
        """Check if service is ready to accept requests."""
        return self.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON response."""
        return {
            "status": self.status.value,
            "components": self.components,
            "timestamp": self.timestamp,
        }


class HealthChecker:
    """Perform comprehensive health checks on service dependencies."""

    def __init__(self, redis_url: str, db_session: AsyncSession):
        self.redis_url = redis_url
        self.db_session = db_session

    async def check_redis(self) -> tuple[HealthStatus, dict[str, Any]]:
        """Check Redis connection and key metrics."""
        try:
            r = redis.from_url(self.redis_url, decode_responses=True)
            
            # Ping
            pong = await r.ping()
            if not pong:
                return HealthStatus.UNHEALTHY, {"redis": "ping_failed"}

            # Check memory usage
            info = await r.info()
            memory_used = info.get("used_memory", 0)
            memory_limit = info.get("maxmemory", 0) or 1_073_741_824  # Default 1GB
            memory_usage_pct = (memory_used / memory_limit * 100) if memory_limit else 0

            # Check consumer groups (for Phase 5 workers)
            consumer_groups = {}
            for stream_name in ["ice:preload", "oob:audit"]:
                try:
                    groups = await r.xinfo_groups(stream_name)
                    consumer_groups[stream_name] = len(groups) if groups else 0
                except Exception:
                    consumer_groups[stream_name] = None

            await r.close()

            status = HealthStatus.HEALTHY
            if memory_usage_pct > 90:
                status = HealthStatus.DEGRADED

            return status, {
                "redis": {
                    "connected": True,
                    "memory_usage_percent": round(memory_usage_pct, 2),
                    "consumer_groups": consumer_groups,
                }
            }
        except Exception as e:
            return HealthStatus.UNHEALTHY, {
                "redis": {
                    "connected": False,
                    "error": str(e),
                }
            }

    async def check_database(self) -> tuple[HealthStatus, dict[str, Any]]:
        """Check database connection and pool status."""
        try:
            # Simple connectivity check
            result = await self.db_session.execute(text("SELECT 1"))
            if result is None:
                return HealthStatus.UNHEALTHY, {"database": "query_failed"}

            # Check connection pool status (if available)
            pool_status = {}
            if hasattr(self.db_session.get_bind(), "pool"):
                pool = self.db_session.get_bind().pool
                pool_status = {
                    "size": pool.size(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                }

            return HealthStatus.HEALTHY, {
                "database": {
                    "connected": True,
                    "pool": pool_status,
                }
            }
        except Exception as e:
            return HealthStatus.UNHEALTHY, {
                "database": {
                    "connected": False,
                    "error": str(e),
                }
            }

    async def check_streams(self) -> tuple[HealthStatus, dict[str, Any]]:
        """Check Redis stream status (input/output streams exist)."""
        try:
            r = redis.from_url(self.redis_url, decode_responses=True)

            stream_status = {}
            for stream_name in [
                "ingress:incoming",
                "bot:lane:default",
                "bot:lane:custom",
                "ice:preload",
                "oob:audit",
                "reply:requests",
                "outbound:requests",
            ]:
                try:
                    info = await r.xinfo_stream(stream_name)
                    stream_status[stream_name] = {
                        "exists": True,
                        "length": info.get("length", 0),
                        "consumer_groups": len(info.get("groups", [])),
                    }
                except redis.ResponseError:
                    # Stream doesn't exist
                    stream_status[stream_name] = {
                        "exists": False,
                    }

            await r.close()

            # All critical streams must exist
            critical_streams = ["ice:preload", "oob:audit"]
            all_exist = all(stream_status.get(s, {}).get("exists", False) for s in critical_streams)

            status = HealthStatus.HEALTHY if all_exist else HealthStatus.DEGRADED

            return status, {
                "streams": stream_status,
            }
        except Exception as e:
            return HealthStatus.DEGRADED, {
                "streams": {
                    "error": str(e),
                }
            }

    async def full_check(self) -> HealthCheckResult:
        """Perform all health checks."""
        redis_status, redis_info = await self.check_redis()
        db_status, db_info = await self.check_database()
        stream_status, stream_info = await self.check_streams()

        # Overall status is worst of all components
        overall_status = min(redis_status, db_status, stream_status, key=lambda s: (s.value != HealthStatus.HEALTHY.value, s.value != HealthStatus.DEGRADED.value))

        components = {
            **redis_info,
            **db_info,
            **stream_info,
        }

        return HealthCheckResult(
            status=overall_status,
            components=components,
        )


class ReadinessChecker:
    """Check if service is ready to accept requests (dependencies available)."""

    def __init__(self, redis_url: str, db_session: AsyncSession):
        self.redis_url = redis_url
        self.db_session = db_session

    async def is_ready(self) -> bool:
        """Check if service is ready."""
        try:
            # Redis must be available
            r = redis.from_url(self.redis_url, decode_responses=True)
            if not await r.ping():
                return False
            await r.close()

            # Database must be accessible
            await self.db_session.execute(text("SELECT 1"))

            return True
        except Exception:
            return False
