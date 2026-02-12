#!/usr/bin/env python3
"""Manually trigger outbox dispatcher"""
import sys
import asyncio

# Add the app to path
sys.path.insert(0, '/app')

from src.app import outbox_dispatcher

async def main():
    print("Manually running outbox dispatcher...")
    processed = await outbox_dispatcher.dispatch_once(batch_size=50)
    print(f"Dispatched {processed} events")

if __name__ == "__main__":
    asyncio.run(main())
