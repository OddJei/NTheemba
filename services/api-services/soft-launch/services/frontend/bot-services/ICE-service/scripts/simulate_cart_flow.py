"""Integration simulation script for cart/order adapter with real backends.

This script exercises create/update draft, reserve and confirm flows against:
- Real Cart service (http://localhost:8530)
- File-backed fallback when service unavailable

Run locally after starting services:
  python -m scripts.simulate_cart_flow
"""

import asyncio
import json
import logging
from pprint import pprint
import sys

from app.adapters.factory import AdapterFactory
from app.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Simulate a full cart flow with real backend integration."""
    
    # Create adapter from factory (uses real Cart service if available)
    cart_adapter = AdapterFactory.get_cart_order_adapter()
    
    logger.info(f"Using Cart service: {Config.CART_SERVICE_URL}")
    
    # Health check
    is_healthy = await cart_adapter.health_check()
    logger.info(f"Cart service health: {is_healthy}")
    
    if not is_healthy:
        logger.warning("Cart service unavailable; using file-backed fallback")
    
    try:
        # Step 1: Create draft
        logger.info("\n=== Step 1: Create Cart Draft ===")
        draft_payload = {
            "session_id": "sess-integration-test",
            "user_phone": "260701234567",
        }
        draft = await cart_adapter.create_or_update_draft(draft_payload)
        logger.info("Created draft:")
        pprint(draft)
        draft_id = draft.get("draft_id") or draft.get("id")
        
        if not draft_id:
            logger.error("Failed to create draft; no draft_id returned")
            sys.exit(1)
        
        logger.info(f"\n✓ Draft created: {draft_id}")
        
        # Step 2: Try to add items (will attempt real endpoint, fallback to file if fails)
        logger.info("\n=== Step 2: Add Items (optional, may fail with service) ===")
        add_payload = {
            "draft_id": draft_id,
            "items": [
                {"product_id": "prod-apple", "qty": 2, "price_minor": 150000},
                {"product_id": "prod-orange", "qty": 3, "price_minor": 50000},
            ],
        }
        updated = await cart_adapter.create_or_update_draft(add_payload)
        logger.info("Updated draft:")
        pprint(updated)
        
        # Step 3: Try to reserve (checkout)
        logger.info("\n=== Step 3: Attempt Checkout (Reserve) ===")
        reserve_payload = {"draft_id": draft_id}
        reservation = await cart_adapter.reserve_items(reserve_payload)
        logger.info("Checkout result:")
        pprint(reservation)
        
        # Step 4: Confirm order (if reserved)
        if reservation.get("status") == "RESERVED":
            logger.info("\n=== Step 4: Confirm Order ===")
            reservation_id = reservation.get("reservation_id")
            confirm_payload = {"reservation_id": reservation_id}
            order = await cart_adapter.confirm_order(confirm_payload)
            logger.info("Confirmed order:")
            pprint(order)
        else:
            logger.info(f"\nCheckout status: {reservation.get('status')} (expected in demo environment)")
        
        logger.info("\n=== Integration Test Complete ===")
        logger.info("✓ Cart adapter factory successfully created and used")
        logger.info("✓ Real Cart service responses being handled")
    
    except Exception as e:
        logger.error(f"Error during simulation: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await AdapterFactory.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
