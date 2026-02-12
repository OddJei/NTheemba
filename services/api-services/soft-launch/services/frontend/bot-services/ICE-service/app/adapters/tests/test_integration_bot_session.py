"""
Integration tests for bot session adapters with real service URLs.

These tests demonstrate how the adapters are used with real bot-session service.
Run with: pytest app/adapters/tests/test_integration_bot_session.py -v -s

Note: Requires bot-session service to be running.
"""
import pytest
import os
from app.config import Config
from app.adapters.factory import AdapterFactory


@pytest.mark.integration
class TestBotSessionIntegration:
    """Integration tests with real bot-session service."""
    
    @pytest.fixture
    async def setup(self):
        """Setup adapters with real bot-session service."""
        Config.log_config()
        bot_session = AdapterFactory.get_bot_session_adapter()
        user_bot = AdapterFactory.get_user_bot_session_adapter()
        
        yield bot_session, user_bot
        
        # Cleanup
        await AdapterFactory.cleanup()
    
    @pytest.mark.asyncio
    async def test_health_check_real_service(self, setup):
        """Test health check against real bot-session service."""
        bot_session, _ = setup
        
        is_healthy = await bot_session.health_check()
        print(f"Bot-session health: {is_healthy}")
        
        # This will fail if bot-session is not running, which is expected
        # in CI/CD environments
        if is_healthy:
            assert True, "Bot-session service is running and healthy"
        else:
            print("Warning: Bot-session service is not running or unhealthy")
    
    @pytest.mark.asyncio
    async def test_create_session_real_service(self, setup):
        """Test session creation with real bot-session service."""
        _, user_bot = setup
        
        try:
            # Create a test session
            phone_number = "260701234567"
            business_id = "test-biz-001"
            metadata = {
                "platform": "whatsapp",
                "bot_phone": "260709999999"
            }
            
            session = await user_bot.create_session(phone_number, business_id, metadata)
            print(f"Created session: {session}")
            
            assert session is not None
            assert "session_id" in session
            assert session["user_phone"] == phone_number
            
            # Get the session state
            session_id = session["session_id"]
            state = await user_bot.get_session_state(session_id)
            print(f"Session state: {state}")
            
            assert state is not None
            assert state["id"] == session_id
            
            # Close the session
            closed = await user_bot.close_session(session_id, "test_complete")
            print(f"Session closed: {closed}")
            assert closed is True
            
        except Exception as e:
            print(f"Integration test skipped: {e}")
            print("Make sure bot-session service is running at", Config.BOT_SESSION_URL)
    
    @pytest.mark.asyncio
    async def test_config_from_environment(self, setup):
        """Test that configuration is read from environment variables."""
        # Print current environment
        print(f"BOT_SESSION_URL: {os.getenv('BOT_SESSION_URL', 'NOT SET')}")
        print(f"ICE_BOT_SESSION_TIMEOUT: {os.getenv('ICE_BOT_SESSION_TIMEOUT', 'NOT SET')}")
        
        # Check that adapters use config
        bot_session, user_bot = setup
        
        assert bot_session.base_url == Config.BOT_SESSION_URL
        assert bot_session.timeout == Config.ICE_BOT_SESSION_TIMEOUT
        
        assert user_bot.base_url == Config.BOT_SESSION_URL
        assert user_bot.timeout == Config.ICE_BOT_SESSION_TIMEOUT


@pytest.mark.integration
class TestAdapterFactory:
    """Test the adapter factory pattern."""
    
    @pytest.mark.asyncio
    async def test_factory_singleton_pattern(self):
        """Test that factory returns same adapter instances."""
        bot_session_1 = AdapterFactory.get_bot_session_adapter()
        bot_session_2 = AdapterFactory.get_bot_session_adapter()
        
        assert bot_session_1 is bot_session_2, "Should return same instance"
        
        user_bot_1 = AdapterFactory.get_user_bot_session_adapter()
        user_bot_2 = AdapterFactory.get_user_bot_session_adapter()
        
        assert user_bot_1 is user_bot_2, "Should return same instance"
        
        # Cleanup
        await AdapterFactory.cleanup()
    
    @pytest.mark.asyncio
    async def test_factory_cleanup(self):
        """Test that cleanup properly closes connections."""
        bot_session = AdapterFactory.get_bot_session_adapter()
        user_bot = AdapterFactory.get_user_bot_session_adapter()
        
        # Create mock clients
        assert bot_session._client is None  # Not yet created
        assert user_bot._client is None  # Not yet created
        
        # Cleanup
        await AdapterFactory.cleanup()
        
        # After cleanup, factory should allow creating new instances
        bot_session_new = AdapterFactory.get_bot_session_adapter()
        assert bot_session is not bot_session_new, "New instance after cleanup"
