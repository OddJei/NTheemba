"""
Unit tests for BotSessionServiceAdapter.

Tests cover:
- Health check success/failure
- Session retrieval (found/not found/error)
- Session persistence (missing endpoint warning)
- Stream operations (not implemented via HTTP)
- HTTP client lifecycle
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from app.adapters.bot_session import BotSessionServiceAdapter


class TestBotSessionServiceAdapter:
    """Test suite for BotSessionServiceAdapter."""
    
    @pytest.fixture
    def adapter(self):
        """Create adapter instance for testing."""
        return BotSessionServiceAdapter(base_url="http://test-bot-session:8000", timeout=1.0)
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, adapter):
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        
        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            result = await adapter.health_check()
            
            assert result is True
            mock_client.get.assert_called_once_with("http://test-bot-session:8000/health")
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, adapter):
        """Test health check when service is down."""
        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_get_client.return_value = mock_client
            
            result = await adapter.health_check()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_health_check_wrong_status(self, adapter):
        """Test health check with wrong status response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "degraded"}
        
        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            result = await adapter.health_check()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_fetch_session_found(self, adapter):
        """Test fetching existing session."""
        session_id = "sess-123"
        expected_data = {
            "id": session_id,
            "user_phone": "260701234567",
            "bot_id": "bot-456",
            "platform": "whatsapp",
            "session_mode": "registered",
            "status": "active",
            "last_event_id": "evt-789"
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_data
        
        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            result = await adapter.fetch_session(session_id)
            
            assert result == expected_data
            mock_client.get.assert_called_once_with(f"http://test-bot-session:8000/session/{session_id}")
    
    @pytest.mark.asyncio
    async def test_fetch_session_not_found(self, adapter):
        """Test fetching non-existent session."""
        session_id = "sess-404"
        mock_response = MagicMock()
        mock_response.status_code = 404
        
        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            result = await adapter.fetch_session(session_id)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_fetch_session_server_error(self, adapter):
        """Test fetching session with server error."""
        session_id = "sess-500"
        mock_response = MagicMock()
        mock_response.status_code = 500
        
        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            result = await adapter.fetch_session(session_id)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_fetch_session_network_error(self, adapter):
        """Test fetching session with network error."""
        session_id = "sess-net-err"
        
        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_get_client.return_value = mock_client
            
            result = await adapter.fetch_session(session_id)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_persist_session_not_implemented(self, adapter):
        """Test persist_session returns False (no endpoint exists)."""
        session_id = "sess-123"
        session_data = {"cart": {"items": []}}
        
        result = await adapter.persist_session(session_id, session_data)
        
        # Should return False since endpoint doesn't exist
        assert result is False
    
    @pytest.mark.asyncio
    async def test_publish_to_stream_not_implemented(self, adapter):
        """Test publish_to_stream raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Use direct Redis client"):
            await adapter.publish_to_stream("ice:hydrated", {"session_id": "sess-123"})
    
    @pytest.mark.asyncio
    async def test_subscribe_to_stream_not_implemented(self, adapter):
        """Test subscribe_to_stream raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Use direct Redis client"):
            await adapter.subscribe_to_stream("ice:preload", "ice-group", "ice-worker-1")
    
    @pytest.mark.asyncio
    async def test_client_lifecycle(self, adapter):
        """Test HTTP client creation and cleanup."""
        # Initially no client
        assert adapter._client is None
        
        # Get client creates it
        client1 = await adapter._get_client()
        assert client1 is not None
        assert adapter._client is client1
        
        # Second call returns same client
        client2 = await adapter._get_client()
        assert client2 is client1
        
        # Close removes client
        await adapter.close()
        assert adapter._client is None
    
    @pytest.mark.asyncio
    async def test_base_url_stripping(self):
        """Test that base_url trailing slashes are stripped."""
        adapter = BotSessionServiceAdapter(base_url="http://test:8000/")
        assert adapter.base_url == "http://test:8000"
        
        adapter2 = BotSessionServiceAdapter(base_url="http://test:8000")
        assert adapter2.base_url == "http://test:8000"
