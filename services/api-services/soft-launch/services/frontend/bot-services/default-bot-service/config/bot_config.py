"""Bot service configuration."""

import logging
from typing import Dict, Any, List
from config.environment import config

logger = logging.getLogger(__name__)

class BotConfig:
    """Bot service configuration management"""
    
    def __init__(self):
        self.config = config
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging configuration"""
        log_level = self.config.get("LOG_LEVEL", "INFO")
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def get_service_config(self) -> Dict[str, Any]:
        """Get service configuration"""
        return {
            "name": self.config.get("SERVICE_NAME"),
            "version": self.config.get("SERVICE_VERSION"),
            "port": self.config.get("SERVICE_PORT"),
            "debug": self.config.get("DEBUG"),
            "log_level": self.config.get("LOG_LEVEL")
        }
    
    def get_redis_config(self) -> Dict[str, Any]:
        """Get Redis configuration"""
        return self.config.get_redis_config()
    
    def get_api_config(self) -> Dict[str, Any]:
        """Get API service configuration"""
        return {
            "auth_service": {
                "url": self.config.get_service_url("AUTH_SERVICE"),
                "timeout": self.config.get_service_timeout("AUTH_SERVICE")
            },
            "session_service": {
                "url": self.config.get_service_url("SESSION_SERVICE"),
                "timeout": self.config.get_service_timeout("SESSION_SERVICE")
            },
            "event_service": {
                "url": self.config.get_service_url("EVENT_SERVICE"),
                "timeout": self.config.get_service_timeout("EVENT_SERVICE")
            },
            "notification_service": {
                "url": self.config.get_service_url("NOTIFICATION_SERVICE"),
                "timeout": self.config.get_service_timeout("NOTIFICATION_SERVICE")
            },
            "catalog_service": {
                "url": self.config.get_service_url("CATALOG_SERVICE"),
                "timeout": self.config.get_service_timeout("CATALOG_SERVICE")
            },
            "order_service": {
                "url": self.config.get_service_url("ORDER_SERVICE"),
                "timeout": self.config.get_service_timeout("ORDER_SERVICE")
            },
            "payment_service": {
                "url": self.config.get_service_url("PAYMENT_SERVICE"),
                "timeout": self.config.get_service_timeout("PAYMENT_SERVICE")
            },
            "inventory_service": {
                "url": self.config.get_service_url("INVENTORY_SERVICE"),
                "timeout": self.config.get_service_timeout("INVENTORY_SERVICE")
            },
            "user_service": {
                "url": self.config.get_service_url("USER_SERVICE"),
                "timeout": self.config.get_service_timeout("USER_SERVICE")
            },
            "business_service": {
                "url": self.config.get_service_url("BUSINESS_SERVICE"),
                "timeout": self.config.get_service_timeout("BUSINESS_SERVICE")
            },
            "affiliate_service": {
                "url": self.config.get_service_url("AFFILIATE_SERVICE"),
                "timeout": self.config.get_service_timeout("AFFILIATE_SERVICE")
            },
            "analytics_service": {
                "url": self.config.get_service_url("ANALYTICS_SERVICE"),
                "timeout": self.config.get_service_timeout("ANALYTICS_SERVICE")
            },
            "report_service": {
                "url": self.config.get_service_url("REPORT_SERVICE"),
                "timeout": self.config.get_service_timeout("REPORT_SERVICE")
            }
        }
    
    def get_queue_config(self) -> Dict[str, Any]:
        """Get queue configuration"""
        return {
            "default_queue": self.config.get("DEFAULT_QUEUE"),
            "reply_queue": self.config.get("REPLY_QUEUE"),
            "event_queue": self.config.get("EVENT_QUEUE"),
            "error_queue": self.config.get("ERROR_QUEUE")
        }
    
    def get_tree_config(self) -> Dict[str, Any]:
        """Get tree configuration"""
        return {
            "cache_ttl": self.config.get("TREE_CACHE_TTL"),
            "load_timeout": self.config.get("TREE_LOAD_TIMEOUT"),
            "default_tree": self.config.get("DEFAULT_TREE")
        }
    
    def get_handler_config(self) -> Dict[str, Any]:
        """Get handler configuration"""
        return {
            "timeout": self.config.get("HANDLER_TIMEOUT"),
            "max_retries": self.config.get("MAX_RETRIES"),
            "retry_delay": self.config.get("RETRY_DELAY")
        }
    
    def get_event_config(self) -> Dict[str, Any]:
        """Get event configuration"""
        return {
            "batch_size": self.config.get("EVENT_BATCH_SIZE"),
            "flush_interval": self.config.get("EVENT_FLUSH_INTERVAL"),
            "retry_attempts": self.config.get("EVENT_RETRY_ATTEMPTS")
        }
    
    def get_security_config(self) -> Dict[str, Any]:
        """Get security configuration"""
        return {
            "api_key_header": self.config.get("API_KEY_HEADER"),
            "api_key_value": self.config.get("API_KEY_VALUE"),
            "jwt_secret": self.config.get("JWT_SECRET"),
            "jwt_expiry": self.config.get("JWT_EXPIRY")
        }
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """Get monitoring configuration"""
        return {
            "health_check_interval": self.config.get("HEALTH_CHECK_INTERVAL"),
            "metrics_enabled": self.config.get("METRICS_ENABLED"),
            "tracing_enabled": self.config.get("TRACING_ENABLED")
        }

    def get_worker_config(self) -> Dict[str, Any]:
        """Get background worker configuration"""
        return {
            "queue_name": self.config.get("DEFAULT_QUEUE"),
            "dlq_name": self.config.get("DEFAULT_QUEUE_DLQ", "default_queue_dlq"),
            "max_workers": int(self.config.get("WORKER_MAX_WORKERS", 10)),
            "max_retries": int(self.config.get("WORKER_MAX_RETRIES", 3)),
            "retry_delay": float(self.config.get("WORKER_RETRY_DELAY", 1.0)),
            "poll_timeout": int(self.config.get("WORKER_POLL_TIMEOUT", 1)),
            "backpressure_threshold": int(self.config.get("WORKER_BACKPRESSURE_THRESHOLD", 1000)),
            # Redis Streams options
            "use_streams": bool(self.config.get("WORKER_USE_STREAMS", False)),
            "stream_name": self.config.get("WORKER_STREAM_NAME", "default_stream"),
            "consumer_group": self.config.get("WORKER_CONSUMER_GROUP", "default_group"),
            "consumer_name": self.config.get("WORKER_CONSUMER_NAME", "consumer_1"),
            "stream_block_ms": int(self.config.get("WORKER_STREAM_BLOCK_MS", 1000)),
            "stream_read_count": int(self.config.get("WORKER_STREAM_READ_COUNT", 1))
        }
    
    def get_all_config(self) -> Dict[str, Any]:
        """Get all configuration"""
        return {
            "service": self.get_service_config(),
            "redis": self.get_redis_config(),
            "api": self.get_api_config(),
            "queue": self.get_queue_config(),
            "tree": self.get_tree_config(),
            "handler": self.get_handler_config(),
            "event": self.get_event_config(),
            "security": self.get_security_config(),
            "monitoring": self.get_monitoring_config()
        }
    
    def validate_config(self) -> bool:
        """Validate configuration"""
        try:
            required_configs = [
                "SERVICE_NAME", "SERVICE_PORT", "REDIS_HOST", "REDIS_PORT"
            ]
            
            for config_key in required_configs:
                if not self.config.get(config_key):
                    logger.error(f"Missing required configuration: {config_key}")
                    return False
            
            # Validate API URLs
            api_config = self.get_api_config()
            for service_name, service_config in api_config.items():
                if not service_config["url"]:
                    logger.error(f"Missing API URL for service: {service_name}")
                    return False
            
            logger.info("Configuration validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False

# Global configuration instance
bot_config = BotConfig()