"""Redis cache layer for ICE service."""

import json
import logging
from typing import Any, Dict, Optional
from datetime import timedelta
import redis.asyncio as redis

from app.config import Config

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis cache operations with TTL and pattern support."""
    
    def __init__(self, redis_url: str = Config.REDIS_URL):
        self.redis_url = redis_url
        self.client: Optional[redis.Redis] = None
    
    async def connect(self) -> None:
        """Connect to Redis."""
        try:
            self.client = await redis.from_url(self.redis_url, decode_responses=True)
            # Test connection
            await self.client.ping()
            logger.info(f"Connected to Redis: {self.redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.client = None
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.client:
            await self.client.close()
            logger.info("Disconnected from Redis")
    
    async def set_session(self, session_id: str, data: Dict[str, Any], ttl_minutes: int = 30) -> bool:
        """Cache session blob."""
        if not self.client:
            return False
        try:
            key = f"cache:session:{session_id}"
            await self.client.setex(key, timedelta(minutes=ttl_minutes), json.dumps(data))
            logger.debug(f"Cached session {session_id} (TTL: {ttl_minutes}m)")
            return True
        except Exception as e:
            logger.error(f"Failed to cache session: {e}")
            return False
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session from cache."""
        if not self.client:
            return None
        try:
            key = f"cache:session:{session_id}"
            data = await self.client.get(key)
            if data:
                logger.debug(f"Cache hit: session {session_id}")
                return json.loads(data)
            logger.debug(f"Cache miss: session {session_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to get session from cache: {e}")
            return None
    
    async def set_catalog(self, business_id: str, data: Dict[str, Any], ttl_minutes: int = 5) -> bool:
        """Cache catalog snapshot."""
        if not self.client:
            return False
        try:
            key = f"cache:catalog:{business_id}"
            await self.client.setex(key, timedelta(minutes=ttl_minutes), json.dumps(data))
            logger.debug(f"Cached catalog for {business_id} (TTL: {ttl_minutes}m)")
            return True
        except Exception as e:
            logger.error(f"Failed to cache catalog: {e}")
            return False
    
    async def get_catalog(self, business_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve catalog from cache."""
        if not self.client:
            return None
        try:
            key = f"cache:catalog:{business_id}"
            data = await self.client.get(key)
            if data:
                logger.debug(f"Cache hit: catalog {business_id}")
                return json.loads(data)
            logger.debug(f"Cache miss: catalog {business_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to get catalog from cache: {e}")
            return None

    async def set_hydrated_session(self, session_id: str, data: Dict[str, Any], ttl_minutes: int = 30) -> bool:
        """Cache hydrated session blob (ICE)."""
        if not self.client:
            return False
        try:
            key = f"cache:hydrated:{session_id}"
            await self.client.setex(key, timedelta(minutes=ttl_minutes), json.dumps(data))
            logger.debug(f"Cached hydrated session {session_id} (TTL: {ttl_minutes}m)")
            return True
        except Exception as e:
            logger.error(f"Failed to cache hydrated session: {e}")
            return False

    async def get_hydrated_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve hydrated session from cache."""
        if not self.client:
            return None
        try:
            key = f"cache:hydrated:{session_id}"
            data = await self.client.get(key)
            if data:
                logger.debug(f"Cache hit: hydrated session {session_id}")
                return json.loads(data)
            logger.debug(f"Cache miss: hydrated session {session_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to get hydrated session from cache: {e}")
            return None

    async def set_product_snapshot(self, product_id: str, data: Dict[str, Any], ttl_minutes: int = 10) -> bool:
        """Cache product snapshot."""
        if not self.client:
            return False
        try:
            key = f"cache:product:{product_id}"
            await self.client.setex(key, timedelta(minutes=ttl_minutes), json.dumps(data))
            logger.debug(f"Cached product {product_id} (TTL: {ttl_minutes}m)")
            return True
        except Exception as e:
            logger.error(f"Failed to cache product: {e}")
            return False

    async def get_product_snapshot(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve product snapshot from cache."""
        if not self.client:
            return None
        try:
            key = f"cache:product:{product_id}"
            data = await self.client.get(key)
            if data:
                logger.debug(f"Cache hit: product {product_id}")
                return json.loads(data)
            logger.debug(f"Cache miss: product {product_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to get product from cache: {e}")
            return None

    async def set_cart(self, cart_id: str, data: Dict[str, Any], ttl_minutes: int = 30) -> bool:
        """Cache cart blob."""
        if not self.client:
            return False
        try:
            key = f"cache:cart:{cart_id}"
            await self.client.setex(key, timedelta(minutes=ttl_minutes), json.dumps(data))
            logger.debug(f"Cached cart {cart_id} (TTL: {ttl_minutes}m)")
            return True
        except Exception as e:
            logger.error(f"Failed to cache cart: {e}")
            return False

    async def get_cart(self, cart_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve cart from cache."""
        if not self.client:
            return None
        try:
            key = f"cache:cart:{cart_id}"
            data = await self.client.get(key)
            if data:
                logger.debug(f"Cache hit: cart {cart_id}")
                return json.loads(data)
            logger.debug(f"Cache miss: cart {cart_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to get cart from cache: {e}")
            return None

    async def set_order_draft(self, order_id: str, data: Dict[str, Any], ttl_minutes: int = 60) -> bool:
        """Cache order draft."""
        if not self.client:
            return False
        try:
            key = f"cache:order:draft:{order_id}"
            await self.client.setex(key, timedelta(minutes=ttl_minutes), json.dumps(data))
            logger.debug(f"Cached order draft {order_id} (TTL: {ttl_minutes}m)")
            return True
        except Exception as e:
            logger.error(f"Failed to cache order draft: {e}")
            return False

    async def get_order_draft(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve order draft from cache."""
        if not self.client:
            return None
        try:
            key = f"cache:order:draft:{order_id}"
            data = await self.client.get(key)
            if data:
                logger.debug(f"Cache hit: order draft {order_id}")
                return json.loads(data)
            logger.debug(f"Cache miss: order draft {order_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to get order draft from cache: {e}")
            return None

    async def set_order_confirmed(self, order_id: str, data: Dict[str, Any], ttl_minutes: int = 120) -> bool:
        """Cache confirmed order snapshot."""
        if not self.client:
            return False
        try:
            key = f"cache:order:confirmed:{order_id}"
            await self.client.setex(key, timedelta(minutes=ttl_minutes), json.dumps(data))
            logger.debug(f"Cached order confirmed {order_id} (TTL: {ttl_minutes}m)")
            return True
        except Exception as e:
            logger.error(f"Failed to cache confirmed order: {e}")
            return False

    async def get_order_confirmed(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve confirmed order from cache."""
        if not self.client:
            return None
        try:
            key = f"cache:order:confirmed:{order_id}"
            data = await self.client.get(key)
            if data:
                logger.debug(f"Cache hit: order confirmed {order_id}")
                return json.loads(data)
            logger.debug(f"Cache miss: order confirmed {order_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to get confirmed order from cache: {e}")
            return None

    async def set_delivery_task(self, delivery_task_id: str, data: Dict[str, Any], ttl_minutes: int = 180) -> bool:
        """Cache delivery task."""
        if not self.client:
            return False
        try:
            key = f"cache:delivery:task:{delivery_task_id}"
            await self.client.setex(key, timedelta(minutes=ttl_minutes), json.dumps(data))
            logger.debug(f"Cached delivery task {delivery_task_id} (TTL: {ttl_minutes}m)")
            return True
        except Exception as e:
            logger.error(f"Failed to cache delivery task: {e}")
            return False

    async def get_delivery_task(self, delivery_task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve delivery task from cache."""
        if not self.client:
            return None
        try:
            key = f"cache:delivery:task:{delivery_task_id}"
            data = await self.client.get(key)
            if data:
                logger.debug(f"Cache hit: delivery task {delivery_task_id}")
                return json.loads(data)
            logger.debug(f"Cache miss: delivery task {delivery_task_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to get delivery task from cache: {e}")
            return None

    async def set_affiliate_context(self, session_id: str, data: Dict[str, Any], ttl_minutes: int = 1440) -> bool:
        """Cache affiliate session context."""
        if not self.client:
            return False
        try:
            key = f"cache:affiliate:session:{session_id}"
            await self.client.setex(key, timedelta(minutes=ttl_minutes), json.dumps(data))
            logger.debug(f"Cached affiliate context {session_id} (TTL: {ttl_minutes}m)")
            return True
        except Exception as e:
            logger.error(f"Failed to cache affiliate context: {e}")
            return False

    async def get_affiliate_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve affiliate session context from cache."""
        if not self.client:
            return None
        try:
            key = f"cache:affiliate:session:{session_id}"
            data = await self.client.get(key)
            if data:
                logger.debug(f"Cache hit: affiliate context {session_id}")
                return json.loads(data)
            logger.debug(f"Cache miss: affiliate context {session_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to get affiliate context from cache: {e}")
            return None

    async def set_hydrate_lock(self, session_id: str, ttl_seconds: int = 30) -> bool:
        """Set single-flight lock for hydration (prevents concurrent hydrations)."""
        return await self.set_lock(f"hydrate:{session_id}", ttl_seconds=ttl_seconds)

    async def release_hydrate_lock(self, session_id: str) -> bool:
        """Release hydration lock."""
        return await self.release_lock(f"hydrate:{session_id}")

    async def set_negative_hydrate_cache(self, session_id: str, ttl_minutes: int = 5) -> bool:
        """Set negative cache for failed hydration (avoid retries)."""
        return await self.set_negative_cache(f"hydrate:{session_id}", ttl_minutes=ttl_minutes)

    async def get_negative_hydrate_cache(self, session_id: str) -> bool:
        """Check if hydration failure is cached."""
        return await self.get_negative_cache(f"hydrate:{session_id}")

    async def delete(self, key_pattern: str) -> int:
        """Delete key(s) by pattern (exact or pattern with *)."""
        if not self.client:
            return 0
        try:
            count = 0
            if "*" in key_pattern:
                cursor = "0"
                while True:
                    cursor, keys = await self.client.scan(cursor, match=key_pattern, count=100)
                    for key in keys:
                        await self.client.delete(key)
                        count += 1
                    if cursor == "0":
                        break
            else:
                count = await self.client.delete(key_pattern)
            logger.debug(f"Deleted {count} key(s) matching pattern: {key_pattern}")
            return count
        except Exception as e:
            logger.error(f"Failed to delete keys: {e}")
            return 0
    
    async def set_lock(self, lock_key: str, ttl_seconds: int = 30) -> bool:
        """Set single-flight lock (for concurrent hydration prevention)."""
        if not self.client:
            return False
        try:
            key = f"lock:{lock_key}"
            result = await self.client.set(key, "1", nx=True, ex=timedelta(seconds=ttl_seconds))
            if result:
                logger.debug(f"Acquired lock: {lock_key}")
                return True
            logger.debug(f"Lock already held: {lock_key}")
            return False
        except Exception as e:
            logger.error(f"Failed to set lock: {e}")
            return False
    
    async def release_lock(self, lock_key: str) -> bool:
        """Release single-flight lock."""
        if not self.client:
            return False
        try:
            key = f"lock:{lock_key}"
            await self.client.delete(key)
            logger.debug(f"Released lock: {lock_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to release lock: {e}")
            return False
    
    async def set_negative_cache(self, neg_key: str, ttl_minutes: int = 5) -> bool:
        """Set negative cache (failure marker to avoid retries)."""
        if not self.client:
            return False
        try:
            key = f"neg:{neg_key}"
            await self.client.setex(key, timedelta(minutes=ttl_minutes), "1")
            logger.debug(f"Set negative cache: {neg_key} (TTL: {ttl_minutes}m)")
            return True
        except Exception as e:
            logger.error(f"Failed to set negative cache: {e}")
            return False
    
    async def get_negative_cache(self, neg_key: str) -> bool:
        """Check if negative cache exists."""
        if not self.client:
            return False
        try:
            key = f"neg:{neg_key}"
            exists = await self.client.exists(key)
            if exists:
                logger.debug(f"Hit negative cache: {neg_key}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to check negative cache: {e}")
            return False
    
    async def publish_event(self, stream_key: str, payload: Dict[str, Any]) -> str:
        """Publish event to Redis stream."""
        if not self.client:
            return ""
        try:
            stream_name = f"stream:{stream_key}"
            msg_id = await self.client.xadd(stream_name, payload)
            logger.debug(f"Published to stream {stream_key}: {msg_id}")
            return str(msg_id)
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            return ""
    
    async def subscribe_to_stream(self, stream_key: str, consumer_group: str, consumer_name: str, count: int = 10) -> list:
        """Subscribe to Redis stream (blocking)."""
        if not self.client:
            return []
        try:
            stream_name = f"stream:{stream_key}"
            # Ensure consumer group exists
            try:
                await self.client.xgroup_create(stream_name, consumer_group, id="$", mkstream=True)
            except redis.ResponseError:
                # Group already exists
                pass
            
            # Read messages
            messages = await self.client.xreadgroup(
                {stream_name: ">"},
                consumer_group,
                consumer_name,
                count=count,
                block=5000  # 5 second timeout
            )
            
            logger.debug(f"Read {len(messages) if messages else 0} messages from {stream_key}")
            return messages or []
        except Exception as e:
            logger.error(f"Failed to subscribe to stream: {e}")
            return []
    
    async def health_check(self) -> bool:
        """Check Redis connectivity."""
        if not self.client:
            return False
        try:
            await self.client.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return False


# Global instance
_redis_cache: Optional[RedisCache] = None


def get_redis_cache() -> RedisCache:
    """Get or create Redis cache instance."""
    global _redis_cache
    if _redis_cache is None:
        _redis_cache = RedisCache()
    return _redis_cache


async def init_redis() -> None:
    """Initialize Redis connection."""
    cache = get_redis_cache()
    await cache.connect()


async def close_redis() -> None:
    """Close Redis connection."""
    cache = get_redis_cache()
    await cache.disconnect()
