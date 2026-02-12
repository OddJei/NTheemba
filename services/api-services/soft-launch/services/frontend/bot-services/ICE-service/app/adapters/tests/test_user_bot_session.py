"""
Unit tests for UserBotConversationAdapter.

Tests cover:
- Health check success/failure
- Session creation (new/reactivated)
- Session state retrieval
- Session closure
- Active sessions query
- Context updates (not implemented via HTTP)
- HTTP client lifecycle
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from app.adapters.user_bot_session import UserBotConversationAdapter


class TestUserBotConversationAdapter:
    """Test suite for UserBotConversationAdapter."""
    
    @pytest.fixture
    def adapter(self):
        """Create adapter instance for testing."""
        return UserBotConversationAdapter(base_url="http://test-bot-session:8000", timeout=1.0)
    
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
    
    @pytest.mark.asyncio
    async def test_create_session_new(self, adapter):
        """Test creating a new session."""
        phone_number = "260701234567"
        business_id = "BIZ-001"
        metadata = {
            "platform": "whatsapp",
            "bot_phone": "260709999999",
            "affiliate_id": "aff-123"
        }
        
        expected_response = {
            "session_id": "sess-new-123",
            "user_phone": phone_number,
            "bot_id": "bot-456",
            "business_id": business_id,
            "platform": "whatsapp",
            "session_mode": "public",
            "status": "active",
            "state": "chat",
            "created_at": "2026-02-04T12:00:00Z",
            "reactivated": False
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = expected_response
        
        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            result = await adapter.create_session(phone_number, business_id, metadata)
            
            assert result == expected_response
            
            # Verify the payload sent
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "http://test-bot-session:8000/session/create"
            payload = call_args[1]["json"]
            assert payload["user_phone"] == phone_number
            assert payload["business_id"] == business_id
            assert payload["platform"] == "whatsapp"
            assert payload["bot_phone"] == "260709999999"
            assert payload["affiliate_id"] == "aff-123"
    
    @pytest.mark.asyncio
    async def test_create_session_reactivated(self, adapter):
        """Test reactivating an existing session."""
        phone_number = "260701234567"
        business_id = "BIZ-001"
        metadata = {
            "platform": "whatsapp",
            "bot_id": "bot-existing"
        }
        
        expected_response = {
            "session_id": "sess-existing-123",
            "user_phone": phone_number,
            "bot_id": "bot-existing",
            "business_id": business_id,
            "platform": "whatsapp",
            "session_mode": "registered",
            "status": "active",
            "state": "cart",
            "created_at": "2026-02-03T12:00:00Z",
            "reactivated": True
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_response
        
        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            result = await adapter.create_session(phone_number, business_id, metadata)
            
            assert result == expected_response
            assert result["reactivated"] is True
    
    @pytest.mark.asyncio
    async def test_create_session_with_affiliate_metadata(self, adapter):
        """Test creating session with full affiliate attribution."""
        phone_number = "260701234567"
        business_id = "BIZ-001"
        metadata = {
            "platform": "whatsapp",
            "bot_phone": "260709999999",
            "affiliate_id": "aff-456",
            "affiliate_metadata": {
                "campaign": "summer-promo",
                "source": "facebook"
            }
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"session_id": "sess-123"}
        
        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            await adapter.create_session(phone_number, business_id, metadata)
            
            # Verify affiliate fields were sent
            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            assert payload["affiliate_id"] == "aff-456"
            assert payload["affiliate_metadata"] == metadata["affiliate_metadata"]
    
    @pytest.mark.asyncio
    async def test_create_session_error(self, adapter):
        """Test session creation with server error."""
        phone_number = "260701234567"
        business_id = "BIZ-001"
        metadata = {"platform": "whatsapp"}
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        
        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            with pytest.raises(Exception, match="Session creation failed: 500"):
                await adapter.create_session(phone_number, business_id, metadata)
    
    @pytest.mark.asyncio
    async def test_get_session_state_found(self, adapter):
        """Test getting session state for existing session."""
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
            
            result = await adapter.get_session_state(session_id)
            
            assert result == expected_data
            mock_client.get.assert_called_once_with(f"http://test-bot-session:8000/session/{session_id}")
    
    @pytest.mark.asyncio
    async def test_get_session_state_not_found(self, adapter):
        """Test getting session state for non-existent session."""
        session_id = "sess-404"
        mock_response = MagicMock()
        mock_response.status_code = 404
        
        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            result = await adapter.get_session_state(session_id)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_update_session_context_not_implemented(self, adapter):
        """Test update_session_context raises NotImplementedError."""
        session_id = "sess-123"
        context_updates = {"cart": {"items": [{"sku": "PROD-001", "qty": 2}]}}
        
        with pytest.raises(NotImplementedError):
            await adapter.update_session_context(session_id, context_updates)
    
    @pytest.mark.asyncio
    async def test_close_session_success(self, adapter):
        """Test closing session successfully."""
        session_id = "sess-123"
        reason = "order_complete"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": session_id,
            "status": "closed",
            "closed_at": "2026-02-04T12:30:00Z"
        }
        
        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            result = await adapter.close_session(session_id, reason)
            
            assert result is True
            mock_client.post.assert_called_once_with(
                f"http://test-bot-session:8000/session/{session_id}/close"
            )
    
    @pytest.mark.asyncio
    async def test_close_session_not_found(self, adapter):
        """Test closing non-existent session."""
        session_id = "sess-404"
        reason = "timeout"
        
        mock_response = MagicMock()
        mock_response.status_code = 404
        
        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            result = await adapter.close_session(session_id, reason)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_close_session_error(self, adapter):
        """Test closing session with network error."""
        session_id = "sess-123"
        reason = "error"
        
        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_get_client.return_value = mock_client
            
            result = await adapter.close_session(session_id, reason)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_active_sessions_found(self, adapter):
        """Test getting active sessions for user."""
        phone_number = "260701234567"
        sessions_data = [
            {"id": "sess-1", "bot_id": "bot-1", "status": "active", "session_mode": "registered"},
            {"id": "sess-2", "bot_id": "bot-2", "status": "active", "session_mode": "public"},
            {"id": "sess-3", "bot_id": "bot-3", "status": "closed", "session_mode": "registered"},
        ]
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sessions_data
        
        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            result = await adapter.get_active_sessions(phone_number)
            
            # Should filter out closed sessions
            assert len(result) == 2
            assert all(s["status"] == "active" for s in result)
            
            # Verify API call
            call_args = mock_client.get.call_args
            assert call_args[0][0] == "http://test-bot-session:8000/session/resolve"
            assert call_args[1]["params"]["user_phone"] == phone_number
    
    @pytest.mark.asyncio
    async def test_get_active_sessions_none_active(self, adapter):
        """Test getting active sessions when all are closed."""
        phone_number = "260701234567"
        sessions_data = [
            {"id": "sess-1", "bot_id": "bot-1", "status": "closed", "session_mode": "registered"},
            {"id": "sess-2", "bot_id": "bot-2", "status": "inactive", "session_mode": "public"},
        ]
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sessions_data
        
        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            result = await adapter.get_active_sessions(phone_number)
            
            assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_get_active_sessions_error(self, adapter):
        """Test getting active sessions with server error."""
        phone_number = "260701234567"
        mock_response = MagicMock()
        mock_response.status_code = 500
        
        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            result = await adapter.get_active_sessions(phone_number)
            
            assert result == []
    
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
