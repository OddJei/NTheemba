"""ICE Service - FastAPI application with bot-facing ingress endpoints.

This service exposes:
1. POST /api/v1/hydrate/session - Hydrate session context for bot-ingress
2. POST /api/v1/reserve - Atomically reserve inventory
3. POST /api/v1/confirm - Confirm order with payment/delivery/affiliate chain
4. GET /api/v1/orders/{order_id}/payment_status - Fetch payment status
5. POST /api/v1/orders/{order_id}/cancel - Cancel confirmed order
6. Health check endpoints
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import Config
from app.cache.redis_client import get_redis_cache
from app.api.routes import health_router, hydration_router, orders_router, messages_router


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


# ============================================================================
# Lifespan Management
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app lifecycle (startup/shutdown)."""
    logger.info("ICE Service starting up...")
    
    # Initialize connections
    try:
        redis = get_redis_cache()
        await redis.connect()
        health = await redis.health_check()
        logger.info(f"Redis health check: {health} (url: {Config.REDIS_URL})")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
    
    yield
    
    try:
        redis = get_redis_cache()
        await redis.disconnect()
    except Exception as e:
        logger.error(f"Redis disconnect failed: {e}")
    
    logger.info("ICE Service shutting down...")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="ICE Service",
    description="Integrated Customer Experience service for bot-facing workflows",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================================
# Register Routers
# ============================================================================

app.include_router(health_router)
app.include_router(hydration_router)
app.include_router(orders_router)
app.include_router(messages_router)


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle uncaught exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "ICE_INTERNAL_ERROR",
            "message": "Internal server error",
        },
    )


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8100,
        log_level="info",
    )
