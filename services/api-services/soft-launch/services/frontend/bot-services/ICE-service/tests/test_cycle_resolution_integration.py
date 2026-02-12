"""Integration tests for cycle resolution end-to-end flow."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from typing import Dict, Any


class TestCycleResolutionIntegration:
    """Integration tests for cycle resolution across ICE and runtime."""

    @pytest.mark.asyncio
    async def test_full_cycle_resolution_flow_completed_cycle(self):
        """Test full flow when last cycle is completed - should start new chat cycle."""
        # This would test the integration between ICE hydration and runtime cycle handling
        # Mock the entire flow from hydration to runtime cycle start

        # Mock bot-session service responses
        mock_cycles = [
            {
                "id": "cycle-1",
                "cycle_state": "delivery",
                "started_at": "2024-01-01T10:00:00Z",
                "completed_at": "2024-01-01T11:00:00Z",  # Completed
                "meta": {
                    "context": {
                        "order_id": "order-123",
                        "delivery_status": "confirmed",
                        "delivery_code": "DEL123"
                    }
                }
            }
        ]

        mock_full_session_data = {
            "session": {"id": "session-123", "user_phone": "260123456789"},
            "cycles": mock_cycles,
            "events": [],
            "order_delivery": []
        }

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            # Mock the admin endpoint response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_full_session_data)
            mock_session.get.return_value.__aenter__.return_value = mock_response

            # Import and test hydration workflow
            from app.orchestration.hydrate import HydrationWorkflow
            workflow = HydrationWorkflow(db=AsyncMock(), redis=AsyncMock())

            # Mock other dependencies
            with patch.object(workflow, '_fetch_user_context', return_value={"user_id": "user-123"}), \
                 patch.object(workflow, '_fetch_business_context', return_value={"profile": {"name": "Test Business"}}), \
                 patch.object(workflow, '_lookup_business_by_phone', return_value={"business_id": "business-123"}), \
                 patch.object(workflow, '_fetch_service_token', return_value="service-token"), \
                 patch.object(workflow, '_fetch_bot_config', return_value={"bot_id": "bot-123"}), \
                 patch.object(workflow, '_resolve_or_create_bot_session', return_value={"session_id": "session-123"}), \
                 patch.object(workflow, '_fetch_catalog_context', return_value={}), \
                 patch.object(workflow, '_fetch_product_snapshots', return_value={}), \
                 patch.object(workflow, '_get_cached_session', return_value={}):

                result = await workflow.hydrate_session(
                    session_id="session-123",
                    phone_number="260123456789",
                    business_id="business-123",
                    business_phone="260987654321"
                )

                # Verify the blob contains cycle resolution metadata
                metadata = result.get("metadata", {})
                cycle_resolution = metadata.get("cycle_resolution", {})

                assert cycle_resolution["last_cycle_completed"] is True
                assert cycle_resolution["should_start_new_chat_cycle"] is True
                assert "order_id" in cycle_resolution["last_cycle_context"]
                assert result["session_state"]["current_node"] == "chat"

    @pytest.mark.asyncio
    async def test_full_cycle_resolution_flow_open_cycle(self):
        """Test full flow when last cycle is open - should reuse existing cycle."""
        # Mock bot-session service responses for open cycle
        mock_cycles = [
            {
                "id": "cycle-1",
                "cycle_state": "order",
                "started_at": "2024-01-01T10:00:00Z",
                "completed_at": None,  # Still open
                "meta": {
                    "context": {
                        "cart_summary": {"total": 150},
                        "selected_items": [{"id": "1", "name": "Test Item"}]
                    }
                }
            }
        ]

        mock_full_session_data = {
            "session": {"id": "session-123", "user_phone": "260123456789"},
            "cycles": mock_cycles,
            "events": [],
            "order_delivery": []
        }

        mock_context_data = {
            "current_state": "order",
            "object_context": {
                "order": {
                    "cart_summary": {"total": 150},
                    "selected_items": [{"id": "1", "name": "Test Item"}]
                }
            }
        }

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            # Mock responses for both calls
            mock_full_response = AsyncMock()
            mock_full_response.status = 200
            mock_full_response.json = AsyncMock(return_value=mock_full_session_data)

            mock_context_response = AsyncMock()
            mock_context_response.status = 200
            mock_context_response.json = AsyncMock(return_value=mock_context_data)

            mock_session.get.side_effect = [mock_full_response, mock_context_response]

            # Import and test hydration workflow
            from app.orchestration.hydrate import HydrationWorkflow
            workflow = HydrationWorkflow(db=AsyncMock(), redis=AsyncMock())

            # Mock other dependencies
            with patch.object(workflow, '_fetch_user_context', return_value={"user_id": "user-123"}), \
                 patch.object(workflow, '_fetch_business_context', return_value={"profile": {"name": "Test Business"}}), \
                 patch.object(workflow, '_lookup_business_by_phone', return_value={"business_id": "business-123"}), \
                 patch.object(workflow, '_fetch_service_token', return_value="service-token"), \
                 patch.object(workflow, '_fetch_bot_config', return_value={"bot_id": "bot-123"}), \
                 patch.object(workflow, '_resolve_or_create_bot_session', return_value={"session_id": "session-123"}), \
                 patch.object(workflow, '_fetch_catalog_context', return_value={}), \
                 patch.object(workflow, '_fetch_product_snapshots', return_value={}), \
                 patch.object(workflow, '_get_cached_session', return_value={}):

                result = await workflow.hydrate_session(
                    session_id="session-123",
                    phone_number="260123456789",
                    business_id="business-123",
                    business_phone="260987654321"
                )

                # Verify the blob contains cycle resolution metadata
                metadata = result.get("metadata", {})
                cycle_resolution = metadata.get("cycle_resolution", {})

                assert cycle_resolution["last_cycle_completed"] is False
                assert cycle_resolution["should_start_new_chat_cycle"] is False
                assert cycle_resolution["cycle_id_to_use"] == "cycle-1"
                assert result["session_state"]["current_node"] == "order"

    @pytest.mark.asyncio
    async def test_runtime_engine_uses_cycle_resolution(self):
        """Test that runtime engine properly uses cycle resolution from ICE."""
        from app.runtime_engine import ensure_session_and_cycle

        # Test case 1: Should start new chat cycle
        mock_ice_response_new_cycle = {
            "session_meta": {
                "current_stage": "chat",
                "cycle_resolution": {
                    "should_start_new_chat_cycle": True,
                    "last_cycle_context": {"completed_order_id": "order-456"}
                }
            }
        }

        mock_ice_client = AsyncMock()
        mock_ice_client.enabled = True
        mock_ice_client.hydrate = AsyncMock(return_value=mock_ice_response_new_cycle)

        with patch("app.runtime_engine.start_cycle") as mock_start_cycle:
            mock_start_cycle.return_value = {"session_id": "session-123", "cycle_type": "chat"}

            session_id, cycle_id, stage = await ensure_session_and_cycle(
                payload={"from": "260123456789"},
                session_id="session-123",
                bot_meta={"bot_id": "bot-123"},
                business_meta={"id": "business-123"},
                event_id="event-123",
                ice_client=mock_ice_client
            )

            assert session_id == "session-123"
            assert cycle_id == "session-123:chat"  # Redis key format
            assert stage == "chat"
            mock_start_cycle.assert_called_once_with(
                "session-123",
                "chat",
                meta={"previous_context": {"completed_order_id": "order-456"}}
            )

        # Test case 2: Should reuse existing cycle
        mock_ice_response_reuse = {
            "session_meta": {
                "current_stage": "cart",
                "current_cycle_id": "existing-cycle-789",
                "cycle_resolution": {
                    "should_start_new_chat_cycle": False,
                    "cycle_id_to_use": "existing-cycle-789"
                }
            }
        }

        mock_ice_client.hydrate = AsyncMock(return_value=mock_ice_response_reuse)

        with patch("app.runtime_engine.start_cycle") as mock_start_cycle:
            session_id, cycle_id, stage = await ensure_session_and_cycle(
                payload={"from": "260123456789"},
                session_id="session-123",
                bot_meta={"bot_id": "bot-123"},
                business_meta={"id": "business-123"},
                event_id="event-123",
                ice_client=mock_ice_client
            )

            assert session_id == "session-123"
            assert cycle_id == "existing-cycle-789"
            assert stage == "cart"
            mock_start_cycle.assert_not_called()