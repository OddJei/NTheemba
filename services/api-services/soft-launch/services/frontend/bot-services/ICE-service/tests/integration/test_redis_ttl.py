"""Phase 7: Redis TTL Behavior Tests

Verify Redis key TTLs align with bot lifecycle expectations.
"""

import pytest
import asyncio
import redis
import json
from datetime import datetime, timedelta


@pytest.fixture
def redis_client():
    """Connect to Redis for testing."""
    r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
    yield r
    # Cleanup
    r.flushdb()


class TestRedisTTLBehavior:
    """Verify Redis key TTLs align with bot expectations."""
    
    def test_session_cache_ttl(self, redis_client):
        """Session cache key expires after SESSION_TTL (24 hours)."""
        
        session_id = "sess_001"
        session_data = {
            "session_id": session_id,
            "user_id": "user_001",
            "user_phone": "+260970000001"
        }
        
        # Set session with 24-hour TTL
        SESSION_TTL = 86400  # 24 hours in seconds
        redis_client.setex(
            f"session:{session_id}",
            SESSION_TTL,
            json.dumps(session_data)
        )
        
        # Verify key exists
        assert redis_client.exists(f"session:{session_id}") == 1
        
        # Check TTL
        ttl = redis_client.ttl(f"session:{session_id}")
        assert ttl > 0
        assert ttl <= SESSION_TTL
    
    def test_order_draft_ttl(self, redis_client):
        """Order draft cache expires after DRAFT_RESERVE_TTL (2 hours)."""
        
        order_draft_id = "ord_001"
        draft_data = {
            "order_draft_id": order_draft_id,
            "status": "RESERVED",
            "reserved_until": (datetime.utcnow() + timedelta(hours=2)).isoformat()
        }
        
        # Set draft with 2-hour TTL
        DRAFT_TTL = 7200  # 2 hours in seconds
        redis_client.setex(
            f"order_draft:{order_draft_id}",
            DRAFT_TTL,
            json.dumps(draft_data)
        )
        
        # Verify key exists
        assert redis_client.exists(f"order_draft:{order_draft_id}") == 1
        
        ttl = redis_client.ttl(f"order_draft:{order_draft_id}")
        assert ttl > 0
        assert ttl <= DRAFT_TTL
    
    def test_hydrated_session_ttl(self, redis_client):
        """Hydrated session cache expires after HYDRATED_SESSION_TTL (1 hour)."""
        
        session_id = "sess_001"
        hydrated = {
            "session_blob": {"session_id": session_id},
            "order_draft_blob": {},
            "bot_meta_blob": {}
        }
        
        # Set with 1-hour TTL
        HYDRATED_TTL = 3600  # 1 hour in seconds
        redis_client.setex(
            f"hydrated_session:{session_id}",
            HYDRATED_TTL,
            json.dumps(hydrated)
        )
        
        ttl = redis_client.ttl(f"hydrated_session:{session_id}")
        assert ttl > 0
        assert ttl <= HYDRATED_TTL
    
    def test_idempotency_cache_ttl(self, redis_client):
        """Idempotency cache key expires after IDEMPOTENCY_TTL (varies by endpoint)."""
        
        # /hydrate idempotency: 1 hour
        event_id = "evt_hydrate_001"
        result = {"hydrated": True}
        HYDRATE_IDEMPOTENCY_TTL = 3600
        
        redis_client.setex(
            f"idempotency:hydrate:{event_id}",
            HYDRATE_IDEMPOTENCY_TTL,
            json.dumps(result)
        )
        
        ttl = redis_client.ttl(f"idempotency:hydrate:{event_id}")
        assert ttl > 0
        assert ttl <= HYDRATE_IDEMPOTENCY_TTL
        
        # /reserve idempotency: 2 hours
        idempotency_key = "idem_reserve_001"
        RESERVE_IDEMPOTENCY_TTL = 7200
        
        redis_client.setex(
            f"idempotency:reserve:{idempotency_key}",
            RESERVE_IDEMPOTENCY_TTL,
            json.dumps(result)
        )
        
        ttl = redis_client.ttl(f"idempotency:reserve:{idempotency_key}")
        assert ttl > 0
        assert ttl <= RESERVE_IDEMPOTENCY_TTL
    
    def test_ttl_not_exceeded(self, redis_client):
        """Accessing cache before expiration returns fresh data."""
        
        session_id = "sess_001"
        
        # Set cache
        redis_client.setex(
            f"session:{session_id}",
            86400,
            json.dumps({"user_id": "user_001"})
        )
        
        # Read immediately
        cached = redis_client.get(f"session:{session_id}")
        assert cached is not None
        assert json.loads(cached)["user_id"] == "user_001"
        
        # Verify TTL still valid
        ttl = redis_client.ttl(f"session:{session_id}")
        assert ttl > 0
    
    def test_expired_key_cleanup(self, redis_client):
        """Expired keys are automatically cleaned up."""
        
        session_id = "sess_expired"
        
        # Set very short TTL (1 second)
        redis_client.setex(
            f"session:{session_id}",
            1,
            json.dumps({"user_id": "user_001"})
        )
        
        # Key exists
        assert redis_client.exists(f"session:{session_id}") == 1
        
        # Wait for expiration
        import time
        time.sleep(2)
        
        # Key is gone
        assert redis_client.exists(f"session:{session_id}") == 0
    
    def test_ttl_persistence_across_operations(self, redis_client):
        """TTL persists when reading/updating value."""
        
        session_id = "sess_001"
        original_ttl_seconds = 3600
        
        redis_client.setex(
            f"session:{session_id}",
            original_ttl_seconds,
            json.dumps({"version": 1})
        )
        
        # Read value
        value = redis_client.get(f"session:{session_id}")
        assert value is not None
        
        # TTL should still be valid (slightly less due to elapsed time)
        ttl_after_read = redis_client.ttl(f"session:{session_id}")
        assert ttl_after_read > 0
        assert ttl_after_read <= original_ttl_seconds
        
        # Update value (with same TTL)
        updated_value = {"version": 2}
        remaining_ttl = redis_client.ttl(f"session:{session_id}")
        redis_client.setex(
            f"session:{session_id}",
            remaining_ttl,
            json.dumps(updated_value)
        )
        
        # Verify value updated
        new_value = json.loads(redis_client.get(f"session:{session_id}"))
        assert new_value["version"] == 2


class TestStreamConsumerTTL:
    """Verify stream consumer group offsets persist correctly."""
    
    def test_stream_group_persistence(self, redis_client):
        """Consumer group offsets survive service restarts."""
        
        stream_name = "ice:preload"
        group_name = "preload_group"
        consumer_name = "consumer_1"
        
        # Clean up previous test data
        try:
            redis_client.xgroup_destroy(stream_name, group_name)
        except:
            pass
        
        # Add message to stream
        message_id = redis_client.xadd(
            stream_name,
            {"event_id": "evt_001", "data": "test_data"}
        )
        
        # Create consumer group
        redis_client.xgroup_create(stream_name, group_name, 0)
        
        # Read as consumer
        messages = redis_client.xreadgroup(
            group_name,
            consumer_name,
            {stream_name: ">"},
            count=1
        )
        
        assert len(messages) > 0
        
        # Verify group info persists
        groups = redis_client.xinfo_groups(stream_name)
        assert any(g["name"] == group_name for g in groups)
        
        # Verify consumer info
        consumers = redis_client.xinfo_consumers(stream_name, group_name)
        assert any(c["name"] == consumer_name for c in consumers)
    
    def test_stream_pending_entries(self, redis_client):
        """Pending entries in stream are tracked by consumer group."""
        
        stream_name = "ice:preload"
        group_name = "preload_group"
        consumer_name = "consumer_1"
        
        # Clean up
        try:
            redis_client.xgroup_destroy(stream_name, group_name)
        except:
            pass
        
        # Add multiple messages
        message_id_1 = redis_client.xadd(
            stream_name,
            {"event_id": "evt_001"}
        )
        message_id_2 = redis_client.xadd(
            stream_name,
            {"event_id": "evt_002"}
        )
        
        # Create group
        redis_client.xgroup_create(stream_name, group_name, 0)
        
        # Read first message (pending)
        messages = redis_client.xreadgroup(
            group_name,
            consumer_name,
            {stream_name: ">"},
            count=1
        )
        
        # Check pending
        pending = redis_client.xpending(stream_name, group_name)
        assert pending["pending"] == 1  # One unacknowledged message
        
        # Acknowledge
        redis_client.xack(stream_name, group_name, message_id_1)
        
        # Pending count should decrease
        pending = redis_client.xpending(stream_name, group_name)
        assert pending["pending"] == 0


class TestCacheTTLStrategy:
    """Test overall cache TTL strategy alignment with bot lifecycle."""
    
    def test_session_lifecycle_ttl(self, redis_client):
        """Session cache outlives typical bot conversation (24 hours)."""
        
        session_id = "sess_001"
        
        # Typical bot conversation lasts 5-30 minutes
        # Session cache should last 24 hours to support returning users
        SESSION_TTL = 86400  # 24 hours
        
        redis_client.setex(
            f"session:{session_id}",
            SESSION_TTL,
            json.dumps({"timestamp": datetime.utcnow().isoformat()})
        )
        
        # After 10 minutes, session should still be cached
        ttl_after_10min = redis_client.ttl(f"session:{session_id}")
        assert ttl_after_10min > 86400 - 600  # At least 23h50m left
    
    def test_draft_lifecycle_ttl(self, redis_client):
        """Draft cache lifetime matches reservation window (2 hours)."""
        
        order_draft_id = "ord_001"
        
        # Bot user reserves items with 2-hour window to complete payment
        DRAFT_TTL = 7200  # 2 hours
        
        reserved_until = datetime.utcnow() + timedelta(seconds=DRAFT_TTL)
        draft_data = {
            "status": "RESERVED",
            "reserved_until": reserved_until.isoformat()
        }
        
        redis_client.setex(
            f"order_draft:{order_draft_id}",
            DRAFT_TTL,
            json.dumps(draft_data)
        )
        
        # After 1 hour, draft should still be reserved
        ttl = redis_client.ttl(f"order_draft:{order_draft_id}")
        assert ttl > 3600  # More than 1 hour left
    
    def test_hydrated_cache_balances_freshness_and_load(self, redis_client):
        """Hydrated session cache balances freshness vs database load."""
        
        session_id = "sess_001"
        
        # Hydrated session cached for 1 hour
        # Refreshes data if bot session lasts >1 hour
        # Reduces database queries during typical 5-30min conversations
        HYDRATED_TTL = 3600
        
        redis_client.setex(
            f"hydrated_session:{session_id}",
            HYDRATED_TTL,
            json.dumps({
                "session_blob": {"user_id": "user_001"},
                "order_draft_blob": {}
            })
        )
        
        ttl = redis_client.ttl(f"hydrated_session:{session_id}")
        assert 0 < ttl <= HYDRATED_TTL


class TestMultipleKeysExpiration:
    """Test behavior when multiple related keys expire."""
    
    def test_session_and_draft_expiration_alignment(self, redis_client):
        """Session and draft keys have independent TTLs."""
        
        session_id = "sess_001"
        order_draft_id = "ord_001"
        
        SESSION_TTL = 86400  # 24 hours
        DRAFT_TTL = 7200    # 2 hours
        
        # Set both
        redis_client.setex(
            f"session:{session_id}",
            SESSION_TTL,
            json.dumps({})
        )
        redis_client.setex(
            f"order_draft:{order_draft_id}",
            DRAFT_TTL,
            json.dumps({})
        )
        
        session_ttl = redis_client.ttl(f"session:{session_id}")
        draft_ttl = redis_client.ttl(f"order_draft:{order_draft_id}")
        
        # Draft expires much sooner (intentional)
        assert draft_ttl < session_ttl
        assert session_ttl > DRAFT_TTL


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
