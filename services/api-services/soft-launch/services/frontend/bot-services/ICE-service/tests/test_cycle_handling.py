"""Tests for cycle resolution logic in ICE and runtime engine."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any


class TestCycleResolution:
    """Test cycle resolution functionality."""

    @pytest.mark.asyncio
    async def test_resolve_cycle_state_completed_cycle(self):
        """Test resolving when last cycle is completed."""
        from app.orchestration.hydrate import HydrationWorkflow

        # Mock the bot-session response
        mock_cycles = [
            {
                "id": "cycle-1",
                "cycle_state": "order",
                "started_at": "2024-01-01T10:00:00Z",
                "completed_at": "2024-01-01T10:30:00Z",  # Completed
                "meta": {
                    "context": {
                        "cart_items": [{"id": "1", "name": "Test Item"}],
                        "order_summary": {"total": 100}
                    }
                }
            }
        ]

        mock_full_data = {
            "session": {"id": "session-123"},
            "cycles": mock_cycles
        }

        workflow = HydrationWorkflow(db=None, redis=None)

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            # Mock the admin session full endpoint
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_full_data)
            mock_session.get.return_value.__aenter__.return_value = mock_response

            bot_session = {"session_id": "session-123"}
            result = await workflow._resolve_cycle_state_and_context(bot_session, "token-123")

            assert result["current_state"] == "chat"
            assert result["state_context"] == {
                "cart_items": [{"id": "1", "name": "Test Item"}],
                "order_summary": {"total": 100}
            }
            assert result["cycle_resolution"]["last_cycle_completed"] is True
            assert result["cycle_resolution"]["should_start_new_chat_cycle"] is True
            assert result["cycle_resolution"]["cycle_id_to_use"] is None

    @pytest.mark.asyncio
    async def test_resolve_cycle_state_open_cycle(self):
        """Test resolving when last cycle is still open."""
        from app.orchestration.hydrate import HydrationWorkflow

        # Mock the bot-session response
        mock_cycles = [
            {
                "id": "cycle-1",
                "cycle_state": "cart",
                "started_at": "2024-01-01T10:00:00Z",
                "completed_at": None,  # Still open
                "meta": {
                    "context": {
                        "selected_items": [{"id": "1", "name": "Test Item"}]
                    }
                }
            }
        ]

        mock_full_data = {
            "session": {"id": "session-123"},
            "cycles": mock_cycles
        }

        mock_context_data = {
            "current_state": "cart",
            "object_context": {
                "cart": {
                    "selected_items": [{"id": "1", "name": "Test Item"}]
                }
            }
        }

        workflow = HydrationWorkflow(db=None, redis=None)

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            # Mock responses
            mock_full_response = AsyncMock()
            mock_full_response.status = 200
            mock_full_response.json = AsyncMock(return_value=mock_full_data)

            mock_context_response = AsyncMock()
            mock_context_response.status = 200
            mock_context_response.json = AsyncMock(return_value=mock_context_data)

            mock_session.get.side_effect = [
                mock_full_response,  # First call for full data
                mock_context_response  # Second call for context
            ]

            bot_session = {"session_id": "session-123"}
            result = await workflow._resolve_cycle_state_and_context(bot_session, "token-123")

            assert result["current_state"] == "cart"
            assert result["state_context"] == {
                "selected_items": [{"id": "1", "name": "Test Item"}]
            }
            assert result["cycle_resolution"]["last_cycle_completed"] is False
            assert result["cycle_resolution"]["should_start_new_chat_cycle"] is False
            assert result["cycle_resolution"]["cycle_id_to_use"] == "cycle-1"

    @pytest.mark.asyncio
    async def test_resolve_cycle_state_no_cycles(self):
        """Test resolving when no cycles exist yet."""
        from app.orchestration.hydrate import HydrationWorkflow

        mock_full_data = {
            "session": {"id": "session-123"},
            "cycles": []  # No cycles
        }

        workflow = HydrationWorkflow(db=None, redis=None)

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_full_data)
            mock_session.get.return_value.__aenter__.return_value = mock_response

            bot_session = {"session_id": "session-123"}
            result = await workflow._resolve_cycle_state_and_context(bot_session, "token-123")

            assert result["current_state"] == "chat"
            assert result["state_context"] == {}
            assert result["cycle_resolution"]["last_cycle_completed"] is False
            assert result["cycle_resolution"]["should_start_new_chat_cycle"] is True
            assert result["cycle_resolution"]["cycle_id_to_use"] is None


class TestRuntimeCycleHandling:
    """Test cycle handling in runtime engine."""

    @pytest.mark.asyncio
    async def test_ensure_session_and_cycle_with_new_chat_cycle(self):
        """Test that ensure_session_and_cycle starts new chat cycle when needed."""
        from app.runtime_engine import ensure_session_and_cycle

        # Mock ICE response with cycle resolution
        mock_ice_response = {
            "session_meta": {
                "current_stage": "chat",
                "cycle_resolution": {
                    "should_start_new_chat_cycle": True,
                    "last_cycle_context": {"previous_order": "123"}
                }
            }
        }

        mock_ice_client = AsyncMock()
        mock_ice_client.enabled = True
        mock_ice_client.hydrate = AsyncMock(return_value=mock_ice_response)

        payload = {"from": "260123456789", "platform": "whatsapp"}
        bot_meta = {"bot_id": "bot-123"}
        business_meta = {"id": "business-123"}

        with patch("app.runtime_engine.start_cycle") as mock_start_cycle:
            mock_start_cycle.return_value = {"cycle_id": "new-cycle-123"}

            session_id, cycle_id, current_stage = await ensure_session_and_cycle(
                payload=payload,
                session_id="session-123",
                bot_meta=bot_meta,
                business_meta=business_meta,
                event_id="event-123",
                ice_client=mock_ice_client
            )

            assert session_id == "session-123"
            assert cycle_id == "session-123:chat"  # Redis key format
            assert current_stage == "chat"
            mock_start_cycle.assert_called_once_with(
                "session-123",
                "chat",
                meta={"previous_context": {"previous_order": "123"}}
            )

    @pytest.mark.asyncio
    async def test_ensure_session_and_cycle_reuse_open_cycle(self):
        """Test that ensure_session_and_cycle reuses open cycle."""
        from app.runtime_engine import ensure_session_and_cycle

        # Mock ICE response with open cycle
        mock_ice_response = {
            "session_meta": {
                "current_stage": "cart",
                "current_cycle_id": "existing-cycle-123",
                "cycle_resolution": {
                    "should_start_new_chat_cycle": False,
                    "cycle_id_to_use": "existing-cycle-123"
                }
            }
        }

        mock_ice_client = AsyncMock()
        mock_ice_client.enabled = True
        mock_ice_client.hydrate = AsyncMock(return_value=mock_ice_response)

        payload = {"from": "260123456789", "platform": "whatsapp"}
        bot_meta = {"bot_id": "bot-123"}
        business_meta = {"id": "business-123"}

        with patch("app.runtime_engine.start_cycle") as mock_start_cycle:
            session_id, cycle_id, current_stage = await ensure_session_and_cycle(
                payload=payload,
                session_id="session-123",
                bot_meta=bot_meta,
                business_meta=business_meta,
                event_id="event-123",
                ice_client=mock_ice_client
            )

            assert session_id == "session-123"
            assert cycle_id == "existing-cycle-123"
            assert current_stage == "cart"
            mock_start_cycle.assert_not_called()  # Should not start new cycle