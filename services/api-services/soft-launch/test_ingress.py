#!/usr/bin/env python
"""
Quick test script to run bot-ingress listener and check stream outputs.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# Add bot-ingress to path
bot_ingress_dir = Path(__file__).parent / "services" / "frontend" / "bot-services" / "bot-ingress-service"
sys.path.insert(0, str(bot_ingress_dir))

# Set environment variables
os.environ["ICE_SERVICE_URL"] = "http://localhost:8100"
os.environ["INGRESS_HYDRATE_FIRST"] = "True"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

import redis
from app.core.config import get_settings
from app.core.redis import get_redis
from app.workers.queue_listener import start_listener

async def main():
    """Run listener for 5 seconds, then check streams."""
    settings = get_settings()
    redis_client = get_redis(settings)
    
    print(f"✓ Settings loaded")
    print(f"  ICE_SERVICE_URL: {settings.ice_service_url}")
    print(f"  INGRESS_HYDRATE_FIRST: {settings.ingress_hydrate_first}")
    print(f"  REDIS_URL: {settings.redis_url}")
    print(f"  Incoming stream: {settings.incoming_stream}")
    print()
    
    # Start listener in background
    listener_task = asyncio.create_task(start_listener(redis_client, settings))
    
    print("✓ Listener started, running for 8 seconds...")
    await asyncio.sleep(8)
    
    # Cancel listener
    listener_task.cancel()
    try:
        await listener_task
    except asyncio.CancelledError:
        pass
    
    print("✓ Listener stopped")
    print()
    
    # Check streams
    r = redis.from_url(settings.redis_url, decode_responses=True)
    
    resolved = r.xrevrange("ingress:resolved_payload", count=3)
    print(f"📍 ingress:resolved_payload ({len(resolved)} entries):")
    for msg_id, data in resolved:
        print(f"  ID: {msg_id}")
        if "meta" in data:
            meta = json.loads(data["meta"]) if isinstance(data["meta"], str) else data["meta"]
            print(f"    session_state: {meta.get('session_state', 'N/A')}")
            print(f"    request_id: {meta.get('request_id', 'N/A')}")
        print()
    
    lane_custom = r.xrevrange("bot:lane:custom", count=3)
    print(f"📍 bot:lane:custom ({len(lane_custom)} entries):")
    for msg_id, data in lane_custom:
        print(f"  ID: {msg_id}")
        print(f"    message: {data.get('message', 'N/A')[:50]}")
        print()
    
    lane_default = r.xrevrange("bot:lane:default", count=3)
    print(f"📍 bot:lane:default ({len(lane_default)} entries):")
    for msg_id, data in lane_default:
        print(f"  ID: {msg_id}")
        print(f"    message: {data.get('message', 'N/A')[:50]}")
        print()
    
    r.close()

if __name__ == "__main__":
    asyncio.run(main())
