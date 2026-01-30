"""Environment configuration for bot service."""

import os
from typing import Dict, Any

class EnvironmentConfig:
    """Environment configuration management"""
    
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables"""
        debug_flag = os.getenv("DEBUG", "true").lower() == "true"
        catalog_default_url = os.getenv("CATALOG_SERVICE_URL") or (
            "http://127.0.0.1:9101" if debug_flag else "http://localhost:8104"
        )

        return {
            # Service Configuration
            "SERVICE_NAME": os.getenv("SERVICE_NAME", "default-bot-service"),
            "SERVICE_VERSION": os.getenv("SERVICE_VERSION", "1.0.0"),
            "SERVICE_PORT": int(os.getenv("SERVICE_PORT", "8000")),
            "DEBUG": debug_flag,
            "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
            
            # Redis Configuration
            "REDIS_HOST": os.getenv("REDIS_HOST", "localhost"),
            "REDIS_PORT": int(os.getenv("REDIS_PORT", "6379")),
            "REDIS_DB": int(os.getenv("REDIS_DB", "0")),
            "REDIS_PASSWORD": os.getenv("REDIS_PASSWORD", ""),
            "REDIS_TTL": int(os.getenv("REDIS_TTL", "3600")),
            
            # API Service Base URLs (Ports 8100-8199)
            "AUTH_SERVICE_URL": os.getenv("AUTH_SERVICE_URL", "http://localhost:8100"),
            "SESSION_SERVICE_URL": os.getenv("SESSION_SERVICE_URL", "http://localhost:8101"),
            "EVENT_SERVICE_URL": os.getenv("EVENT_SERVICE_URL", "http://localhost:8102"),
            "NOTIFICATION_SERVICE_URL": os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8103"),
            "CATALOG_SERVICE_URL": catalog_default_url,
            "CATALOG_SERVICE_CATEGORIES_PATH": os.getenv("CATALOG_SERVICE_CATEGORIES_PATH", "/categories"),
            "CATALOG_SERVICE_CATEGORIES_ALL_PATH": os.getenv("CATALOG_SERVICE_CATEGORIES_ALL_PATH", "/categories/all"),
            "CATALOG_SERVICE_USE_CATEGORIES_ALL": os.getenv("CATALOG_SERVICE_USE_CATEGORIES_ALL"),
            "ORDER_SERVICE_URL": os.getenv("ORDER_SERVICE_URL", "http://localhost:8105"),
            "PAYMENT_SERVICE_URL": os.getenv("PAYMENT_SERVICE_URL", "http://localhost:8106"),
            "INVENTORY_SERVICE_URL": os.getenv("INVENTORY_SERVICE_URL", "http://localhost:8107"),
            "USER_SERVICE_URL": os.getenv("USER_SERVICE_URL", "http://localhost:8108"),
            "BUSINESS_SERVICE_URL": os.getenv("BUSINESS_SERVICE_URL", "http://localhost:8109"),
            "AFFILIATE_SERVICE_URL": os.getenv("AFFILIATE_SERVICE_URL", "http://localhost:8110"),
            "ANALYTICS_SERVICE_URL": os.getenv("ANALYTICS_SERVICE_URL", "http://localhost:8111"),
            "REPORT_SERVICE_URL": os.getenv("REPORT_SERVICE_URL", "http://localhost:8112"),
            
            # Queue Configuration
            "DEFAULT_QUEUE": os.getenv("DEFAULT_QUEUE", "default_queue"),
            "REPLY_QUEUE": os.getenv("REPLY_QUEUE", "reply_queue"),
            "EVENT_QUEUE": os.getenv("EVENT_QUEUE", "bot_events"),
            "ERROR_QUEUE": os.getenv("ERROR_QUEUE", "error_queue"),
            
            # Tree Configuration
            "TREE_CACHE_TTL": int(os.getenv("TREE_CACHE_TTL", "1800")),
            "TREE_LOAD_TIMEOUT": int(os.getenv("TREE_LOAD_TIMEOUT", "30")),
            "DEFAULT_TREE": os.getenv("DEFAULT_TREE", "public_catalog_tree"),
            
            # Handler Configuration
            "HANDLER_TIMEOUT": int(os.getenv("HANDLER_TIMEOUT", "30")),
            "MAX_RETRIES": int(os.getenv("MAX_RETRIES", "3")),
            "RETRY_DELAY": int(os.getenv("RETRY_DELAY", "1")),
            
            # Event Configuration
            "EVENT_BATCH_SIZE": int(os.getenv("EVENT_BATCH_SIZE", "100")),
            "EVENT_FLUSH_INTERVAL": int(os.getenv("EVENT_FLUSH_INTERVAL", "5")),
            "EVENT_RETRY_ATTEMPTS": int(os.getenv("EVENT_RETRY_ATTEMPTS", "3")),
            
            # Security Configuration
            "API_KEY_HEADER": os.getenv("API_KEY_HEADER", "X-API-Key"),
            "API_KEY_VALUE": os.getenv("API_KEY_VALUE", "your-api-key-here"),
            "JWT_SECRET": os.getenv("JWT_SECRET", "your-jwt-secret-here"),
            "JWT_EXPIRY": int(os.getenv("JWT_EXPIRY", "3600")),
            
            # Monitoring Configuration
            "HEALTH_CHECK_INTERVAL": int(os.getenv("HEALTH_CHECK_INTERVAL", "30")),
            "METRICS_ENABLED": os.getenv("METRICS_ENABLED", "true").lower() == "true",
            "TRACING_ENABLED": os.getenv("TRACING_ENABLED", "true").lower() == "true",
            
            # External Service Timeouts (seconds)
            "AUTH_SERVICE_TIMEOUT": int(os.getenv("AUTH_SERVICE_TIMEOUT", "10")),
            "SESSION_SERVICE_TIMEOUT": int(os.getenv("SESSION_SERVICE_TIMEOUT", "10")),
            "EVENT_SERVICE_TIMEOUT": int(os.getenv("EVENT_SERVICE_TIMEOUT", "15")),
            "NOTIFICATION_SERVICE_TIMEOUT": int(os.getenv("NOTIFICATION_SERVICE_TIMEOUT", "20")),
            "CATALOG_SERVICE_TIMEOUT": int(os.getenv("CATALOG_SERVICE_TIMEOUT", "15")),
            "ORDER_SERVICE_TIMEOUT": int(os.getenv("ORDER_SERVICE_TIMEOUT", "20")),
            "PAYMENT_SERVICE_TIMEOUT": int(os.getenv("PAYMENT_SERVICE_TIMEOUT", "30")),
            "INVENTORY_SERVICE_TIMEOUT": int(os.getenv("INVENTORY_SERVICE_TIMEOUT", "10")),
            "USER_SERVICE_TIMEOUT": int(os.getenv("USER_SERVICE_TIMEOUT", "10")),
            "BUSINESS_SERVICE_TIMEOUT": int(os.getenv("BUSINESS_SERVICE_TIMEOUT", "15")),
            "AFFILIATE_SERVICE_TIMEOUT": int(os.getenv("AFFILIATE_SERVICE_TIMEOUT", "15")),
            "ANALYTICS_SERVICE_TIMEOUT": int(os.getenv("ANALYTICS_SERVICE_TIMEOUT", "20")),
            "REPORT_SERVICE_TIMEOUT": int(os.getenv("REPORT_SERVICE_TIMEOUT", "30")),
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)
    
    def get_service_url(self, service_name: str) -> str:
        """Get service URL by name"""
        url_key = f"{service_name.upper()}_SERVICE_URL"
        return self.get(url_key, f"http://localhost:8100")
    
    def get_service_timeout(self, service_name: str) -> int:
        """Get service timeout by name"""
        timeout_key = f"{service_name.upper()}_SERVICE_TIMEOUT"
        return self.get(timeout_key, 10)
    
    def is_debug(self) -> bool:
        """Check if debug mode is enabled"""
        return self.get("DEBUG", False)
    
    def get_redis_config(self) -> Dict[str, Any]:
        """Get Redis configuration"""
        return {
            "host": self.get("REDIS_HOST"),
            "port": self.get("REDIS_PORT"),
            "db": self.get("REDIS_DB"),
            "password": self.get("REDIS_PASSWORD"),
            "ttl": self.get("REDIS_TTL")
        }

# Global configuration instance
config = EnvironmentConfig()



