"""Main entry point for default bot service."""

import logging
import asyncio
from typing import Dict, Any
from datetime import datetime
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from config.bot_config import bot_config
from controllers.default_bot_controller import DefaultBotController
from services.queue_worker import RedisQueueWorker
try:
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except Exception:
    PROMETHEUS_AVAILABLE = False

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Default Bot Service",
    description="Bot service for handling user interactions and tree-based conversations",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize bot controller
try:
    bot_controller = DefaultBotController()
    logger.info("Bot controller initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize bot controller: {e}")
    bot_controller = None

# Worker instance (created at startup)
queue_worker: RedisQueueWorker | None = None

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Default Bot Service",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if not bot_controller:
        raise HTTPException(status_code=503, detail="Bot controller not initialized")
    
    health_status = bot_controller.get_health_status()
    status_code = 200 if health_status["status"] == "healthy" else 503
    
    return JSONResponse(
        status_code=status_code,
        content=health_status
    )

@app.post("/bot/message")
async def process_message(request: Request):
    """Process bot message endpoint"""
    if not bot_controller:
        raise HTTPException(status_code=503, detail="Bot controller not initialized")
    
    try:
        # Get request data
        data = await request.json()
        session_id = data.get("session_id")
        payload = data.get("payload", {})
        
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")
        
        # Process message
        response = bot_controller.process_message(session_id, payload)
        
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def _startup_event():
    """Start background worker that listens on Redis queue 'default_queue'."""
    global queue_worker
    if not bot_controller:
        logger.warning("Bot controller not initialized; skipping queue worker startup")
        return

    try:
        worker_cfg = bot_config.get_worker_config()
        queue_worker = RedisQueueWorker(
            bot_controller.redis_client,
            bot_controller,
            queue_name=worker_cfg.get("queue_name", "default_queue"),
            dlq_name=worker_cfg.get("dlq_name"),
            max_workers=worker_cfg.get("max_workers", 10),
            max_retries=worker_cfg.get("max_retries", 3),
            retry_delay=worker_cfg.get("retry_delay", 1.0),
            poll_timeout=worker_cfg.get("poll_timeout", 1),
            backpressure_threshold=worker_cfg.get("backpressure_threshold", 1000),
            use_streams=worker_cfg.get("use_streams", False),
            stream_name=worker_cfg.get("stream_name", "default_stream"),
            consumer_group=worker_cfg.get("consumer_group", "default_group"),
            consumer_name=worker_cfg.get("consumer_name", "consumer_1"),
            stream_block_ms=worker_cfg.get("stream_block_ms", 1000),
            stream_read_count=worker_cfg.get("stream_read_count", 1),
        )
        # start may be coroutine (async worker)
        start_result = queue_worker.start()
        if asyncio.iscoroutine(start_result):
            await start_result
        logger.info("Queue worker started")
    except Exception as e:
        logger.exception("Failed to start queue worker: %s", e)


@app.on_event("shutdown")
async def _shutdown_event():
    """Stop background worker gracefully on shutdown."""
    global queue_worker
    if queue_worker:
        try:
            stop_result = queue_worker.stop()
            if asyncio.iscoroutine(stop_result):
                await stop_result
            logger.info("Queue worker stopped")
        except Exception:
            logger.exception("Error while stopping queue worker")


@app.get("/bot/queue-health")
async def queue_health():
    """Return basic health/metrics about the queue worker and Redis queue."""
    if not bot_controller:
        raise HTTPException(status_code=503, detail="Bot controller not initialized")

    try:
        cfg = bot_config.get_worker_config()
        qname = cfg.get("queue_name", "default_queue")
        qlen = None
        try:
            qlen = bot_controller.redis_client.redis_client.llen(qname)
        except Exception:
            qlen = None

        metrics = {
            "queue": qname,
            "queue_length": qlen,
            "processed": getattr(queue_worker, "processed", 0) if queue_worker else 0,
            "errors": getattr(queue_worker, "errors", 0) if queue_worker else 0,
            "retries": getattr(queue_worker, "retries", 0) if queue_worker else 0,
            "dlq_count": getattr(queue_worker, "dlq_count", 0) if queue_worker else 0,
        }

        status_code = 200
        return JSONResponse(status_code=status_code, content={"worker_metrics": metrics})

    except Exception as e:
        logger.exception("Failed to read queue health: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def metrics():
    """Expose Prometheus metrics if prometheus_client is installed."""
    if not PROMETHEUS_AVAILABLE:
        raise HTTPException(status_code=404, detail="Prometheus client not available. Install prometheus_client to enable metrics")
    try:
        data = generate_latest()
        # return raw bytes with correct content type
        return JSONResponse(content=data, media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.exception("Failed to generate metrics: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/bot/session/create")
async def create_session(request: Request):
    """Create new session endpoint"""
    if not bot_controller:
        raise HTTPException(status_code=503, detail="Bot controller not initialized")
    
    try:
        data = await request.json()
        session_id = data.get("session_id")
        user_id = data.get("user_id")
        session_mode = data.get("session_mode", "public")
        
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")
        
        # Create session payload
        payload = {
            "user_id": user_id,
            "session_mode": session_mode,
            "session_data": data.get("session_data", {})
        }
        
        # Process message to create session
        response = bot_controller.process_message(session_id, payload)
        
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/bot/session/{session_id}")
async def get_session(session_id: str):
    """Get session information"""
    if not bot_controller:
        raise HTTPException(status_code=503, detail="Bot controller not initialized")
    
    try:
        # Get session from Redis
        session_context = bot_controller.redis_client.get_session(session_id)
        
        if not session_context:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return JSONResponse(content={
            "session_id": session_id,
            "user_context": session_context.user_context.__dict__,
            "tree_state": session_context.tree_state.__dict__,
            "session_data": session_context.session_data,
            "created_at": session_context.created_at.isoformat(),
            "last_activity": session_context.last_activity.isoformat(),
            "status": session_context.status
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/bot/session/{session_id}")
async def delete_session(session_id: str):
    """Delete session"""
    if not bot_controller:
        raise HTTPException(status_code=503, detail="Bot controller not initialized")
    
    try:
        # Delete session from Redis
        success = bot_controller.redis_client.delete_session(session_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return JSONResponse(content={
            "success": True,
            "message": f"Session {session_id} deleted successfully"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/bot/cleanup")
async def cleanup_sessions():
    """Cleanup expired sessions"""
    if not bot_controller:
        raise HTTPException(status_code=503, detail="Bot controller not initialized")
    
    try:
        result = bot_controller.cleanup_expired_sessions()
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"Error cleaning up sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/bot/config")
async def get_config():
    """Get service configuration"""
    try:
        config_data = bot_config.get_all_config()
        return JSONResponse(content=config_data)
        
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/bot/trees")
async def get_available_trees():
    """Get available intent trees"""
    if not bot_controller:
        raise HTTPException(status_code=503, detail="Bot controller not initialized")
    
    try:
        # Get available trees from Redis
        trees = bot_controller.redis_client.get_available_trees()
        return JSONResponse(content={"trees": trees})
        
    except Exception as e:
        logger.error(f"Error getting trees: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/bot/trees/{tree_name}/load")
async def load_tree(tree_name: str):
    """Load specific intent tree"""
    if not bot_controller:
        raise HTTPException(status_code=503, detail="Bot controller not initialized")
    
    try:
        # Load tree
        tree = bot_controller.tree_loader.load_tree(tree_name)
        
        if not tree:
            raise HTTPException(status_code=404, detail=f"Tree {tree_name} not found")
        
        return JSONResponse(content={
            "success": True,
            "tree_name": tree_name,
            "tree": tree.__dict__
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading tree: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc),
            "timestamp": datetime.now().isoformat()
        }
    )

def main():
    """Main function to run the service"""
    try:
        # Get configuration
        service_config = bot_config.get_service_config()
        port = service_config["port"]
        debug = service_config["debug"]
        
        logger.info(f"Starting Default Bot Service on port {port}")
        logger.info(f"Debug mode: {debug}")
        
        # Run the service
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=port,
            reload=debug,
            log_level="info"
        )
        
    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        raise

if __name__ == "__main__":
    main()