"""Integration test for MSME and Affiliate adapters.

This script tests:
1. MSME business profile fetching
2. MSME business policies and entitlements
3. Affiliate context hydration (if affiliate code provided)
4. Attribution event emission (order conversion tracking)
"""

import asyncio
import logging
from uuid import uuid4

from app.adapters.factory import AdapterFactory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Run MSME and Affiliate adapter integration test."""
    
    business_id = "BIZ-001"
    
    logger.info("=" * 70)
    logger.info("MSME + Affiliate Adapter Integration Test")
    logger.info("=" * 70)
    
    # Get adapters
    msme_adapter = AdapterFactory.get_msme_adapter()
    affiliate_adapter = AdapterFactory.get_affiliate_adapter()
    
    # Test MSME health
    logger.info("\n[MSME] Checking health...")
    msme_ok = await msme_adapter.health_check()
    logger.info(f"MSME health: {'✓' if msme_ok else '✗'}")
    
    if not msme_ok:
        logger.error("MSME service not reachable, skipping tests")
        await AdapterFactory.cleanup()
        return
    
    # Fetch business profile
    logger.info(f"\n[MSME] Fetching business profile for {business_id}...")
    profile = await msme_adapter.fetch_business_profile(business_id)
    if profile:
        logger.info(f"✓ Business profile fetched:")
        logger.info(f"  Name: {profile.get('name')}")
        logger.info(f"  Location: {profile.get('location')}")
        logger.info(f"  Category: {profile.get('category')}")
        logger.info(f"  Owner: {profile.get('owner', {}).get('username')}")
    else:
        logger.info(f"Business profile not found or service error")
    
    # Fetch business policies/entitlements
    logger.info(f"\n[MSME] Fetching business policies for {business_id}...")
    policies = await msme_adapter.fetch_business_policies(business_id)
    if policies:
        logger.info(f"✓ Business policies fetched:")
        logger.info(f"  Plan: {policies.get('plan')}")
        logger.info(f"  Features: {policies.get('features', {})}")
        logger.info(f"  Limits: {policies.get('limits', {})}")
    else:
        logger.info(f"Business policies not found or service error")
    
    # Test Affiliate health
    logger.info("\n[Affiliate] Checking health...")
    affiliate_ok = await affiliate_adapter.health_check()
    logger.info(f"Affiliate health: {'✓' if affiliate_ok else '✗'}")
    
    if not affiliate_ok:
        logger.warning("Affiliate service not reachable, skipping affiliate tests")
        await AdapterFactory.cleanup()
        return
    
    # Test affiliate context hydration
    logger.info("\n[Affiliate] Hydrating affiliate context...")
    affiliate_code = "PARTNER-001"
    hydration_payload = {
        "affiliate_code": affiliate_code,
        "session_id": str(uuid4()),
    }
    
    affiliate_context = await affiliate_adapter.hydrate_affiliate_context(hydration_payload)
    if affiliate_context.get("affiliate_context"):
        logger.info(f"✓ Affiliate context hydrated for code: {affiliate_code}")
        context = affiliate_context["affiliate_context"]
        logger.info(f"  Affiliate: {context.get('affiliate_name', 'N/A')}")
        logger.info(f"  Commission rate: {context.get('commission_rate', 'N/A')}")
    else:
        logger.info(f"Affiliate context not found (code may not exist): {affiliate_code}")
    
    # Test attribution event emission
    logger.info("\n[Affiliate] Emitting attribution event...")
    order_id = f"ORD-{uuid4().hex[:8].upper()}"
    affiliate_id = "AFF-001"
    event_id = str(uuid4())
    
    attribution_payload = {
        "event_id": event_id,
        "order_id": order_id,
        "business_id": business_id,
        "affiliate_id": affiliate_id,
        "amount_minor": 50000,  # 500.00 in minor units
        "order_details": {
            "items": 3,
            "currency": "ZMW",
            "status": "confirmed",
        }
    }
    
    attribution_result = await affiliate_adapter.emit_attribution_event(attribution_payload)
    if attribution_result.get("success"):
        logger.info(f"✓ Attribution event emitted:")
        logger.info(f"  Order: {order_id}")
        logger.info(f"  Business: {business_id}")
        logger.info(f"  Affiliate: {affiliate_id}")
        logger.info(f"  Amount: {attribution_payload['amount_minor']} minor units")
    else:
        logger.info(f"Attribution emission result: {attribution_result.get('error', 'Unknown error')}")
    
    logger.info("\n" + "=" * 70)
    logger.info("✓ MSME + Affiliate integration test complete")
    logger.info("=" * 70)
    
    await AdapterFactory.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
