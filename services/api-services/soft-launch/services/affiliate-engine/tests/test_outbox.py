
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
import uuid

from src.app.models import AffiliateEvent
from src.app.outbox_dispatcher import dispatch_once

def _uuid() -> str:
    return str(uuid.uuid4())

@pytest.mark.asyncio
async def test_outbox_dispatch_marks_events_dispatched(service_root):
    # Setup: Create an event in DB that hasn't been dispatched
    # We need to access the DB. The test infrastructure uses a DB file from env.
    
    # We need to import get_db_session logic or use what's available.
    from src.app.db import get_db_session
    
    event_id = _uuid()
    
    async with get_db_session() as db:
        event = AffiliateEvent(
            event_id=event_id,
            affiliate_id="aff1",
            event_type="campaign_click",
            occurred_at=datetime.now(timezone.utc),
            source="test",
            correlation_id="corr1",
            meta={"foo": "bar"}
        )
        db.add(event)
        await db.commit()
    
    # Mock httpx to intercept the outbound request
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.status_code = 200
        
        # We also need to patch _sink_url because it requires env var or raises
        with patch("src.app.outbox_dispatcher._sink_url", return_value="http://mock-sink/events"):
            # Run dispatch
            processed_count = await dispatch_once(batch_size=10)
            
            assert processed_count == 1
            mock_post.assert_called_once()
            
            # Verify request body
            call_args = mock_post.call_args
            # args[0] is url, kwargs['json'] is body
            assert call_args[0][0] == "http://mock-sink/events"
            body = call_args[1]['json']
            assert body['event_id'] == event_id
            assert body['event_type'] == "campaign_click"

    # Verify event is marked as dispatched in DB
    async with get_db_session() as db:
        result = await db.execute(select(AffiliateEvent).where(AffiliateEvent.event_id == event_id))
        reloaded = result.scalar_one()
        assert reloaded.dispatched_at is not None

@pytest.mark.asyncio
async def test_outbox_dispatch_skips_already_dispatched(service_root):
    from src.app.db import get_db_session
    
    event_id = _uuid()
    
    async with get_db_session() as db:
        event = AffiliateEvent(
            event_id=event_id,
            affiliate_id="aff1",
            event_type="test_event",
            occurred_at=datetime.now(timezone.utc),
            dispatched_at=datetime.now(timezone.utc), # Already dispatched
            source="test"
        )
        db.add(event)
        await db.commit()
        
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
         with patch("src.app.outbox_dispatcher._sink_url", return_value="http://mock-sink/events"):
            processed_count = await dispatch_once(batch_size=10)
            
            assert processed_count == 0
            mock_post.assert_not_called()
