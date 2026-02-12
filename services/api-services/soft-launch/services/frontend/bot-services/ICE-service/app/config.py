"""
Configuration for ICE service adapters and external services.

Supports both local development (ICE service in venv) and Docker Compose deployment:

**LOCAL DEVELOPMENT:**
  ICE service runs locally in venv
  Backend services run in Docker containers
  Set environment variables:
    ENVIRONMENT=local
    BOT_SESSION_URL=http://localhost:8540
    MSME_ENGINE_URL=http://localhost:8500
    etc.

**DOCKER COMPOSE:**
  ICE service runs in container
  All services communicate via container names
  Default URLs use container names (bot-session, msme-engine, etc.)

Environment variables:
- ENVIRONMENT: local, docker, production (default: local)
- BOT_SESSION_URL: URL of bot-session backend service
- MSME_ENGINE_URL: URL of MSME engine service
- ICE_BOT_SESSION_TIMEOUT: HTTP timeout (default: 5.0)
"""
import os
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class Config:
    """ICE service configuration from environment.
    
    Automatically adjusts defaults based on ENVIRONMENT setting.
    """
    
    # Deployment environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "local").lower()
    IS_LOCAL: bool = ENVIRONMENT in ("local", "dev")
    IS_DOCKER: bool = ENVIRONMENT in ("docker", "production")
    
    # Default hosts based on environment
    _DEFAULT_BOT_SESSION_HOST = "localhost" if IS_LOCAL else "bot-session"
    _DEFAULT_MSME_ENGINE_HOST = "localhost" if IS_LOCAL else "msme-engine"
    _DEFAULT_REDIS_HOST = "localhost" if IS_LOCAL else "redis"
    _DEFAULT_POSTGRES_HOST = "localhost" if IS_LOCAL else "postgres"
    
    # Bot Session Service
    BOT_SESSION_URL: str = os.getenv(
        "BOT_SESSION_URL", 
        f"http://{_DEFAULT_BOT_SESSION_HOST}:8540"
    )
    ICE_BOT_SESSION_TIMEOUT: float = float(os.getenv("ICE_BOT_SESSION_TIMEOUT", "5.0"))
    
    # MSME Engine (for authentication and user info)
    MSME_ENGINE_URL: str = os.getenv(
        "MSME_ENGINE_URL",
        f"http://{_DEFAULT_MSME_ENGINE_HOST}:8500"
    )
    MSME_ENGINE_TIMEOUT: float = float(os.getenv("MSME_ENGINE_TIMEOUT", "5.0"))
    
    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", _DEFAULT_REDIS_HOST)
    REDIS_PORT: str = os.getenv("REDIS_PORT", "6379")
    REDIS_URL: str = os.getenv(
        "REDIS_URL",
        f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
    )
    REDIS_TIMEOUT: float = float(os.getenv("REDIS_TIMEOUT", "5.0"))
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        f"postgresql+asyncpg://postgres:!ladybug!%23!@{_DEFAULT_POSTGRES_HOST}:5432/ntheemba"
    )
    
    # Backend Services URLs (for other adapters)
    CATALOG_INVENTORY_URL: str = os.getenv(
        "CATALOG_INVENTORY_URL", 
        "http://localhost:8520" if IS_LOCAL else "http://catalog-inventory:8520"
    )
    CART_SERVICE_URL: str = os.getenv(
        "CART_SERVICE_URL", 
        "http://localhost:8530" if IS_LOCAL else "http://cart:8530"
    )
    PAYMENT_REVENUE_URL: str = os.getenv(
        "PAYMENT_REVENUE_URL", 
        "http://localhost:8590" if IS_LOCAL else "http://payment-revenue:8590"
    )
    ORDER_DELIVERY_URL: str = os.getenv(
        "ORDER_DELIVERY_URL", 
        "http://localhost:8560" if IS_LOCAL else "http://order-delivery:8560"
    )
    AFFILIATE_ENGINE_URL: str = os.getenv(
        "AFFILIATE_ENGINE_URL", 
        "http://localhost:8510" if IS_LOCAL else "http://affiliate-engine:8510"
    )
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Return configuration as dictionary."""
        return {
            "bot_session_url": cls.BOT_SESSION_URL,
            "redis_url": cls.REDIS_URL,
            "database_url": cls.DATABASE_URL,
            "catalog_inventory_url": cls.CATALOG_INVENTORY_URL,
            "cart_service_url": cls.CART_SERVICE_URL,
            "payment_revenue_url": cls.PAYMENT_REVENUE_URL,
            "order_delivery_url": cls.ORDER_DELIVERY_URL,
            "affiliate_engine_url": cls.AFFILIATE_ENGINE_URL,
            "msme_engine_url": cls.MSME_ENGINE_URL,
        }
    
    @classmethod
    def log_config(cls) -> None:
        """Log configuration at startup."""
        logger.info("=" * 60)
        logger.info("ICE Service Configuration")
        logger.info("=" * 60)
        for key, value in cls.to_dict().items():
            # Mask sensitive URLs
            if "password" in str(value).lower():
                value = "***MASKED***"
            logger.info(f"  {key}: {value}")
        logger.info("=" * 60)
