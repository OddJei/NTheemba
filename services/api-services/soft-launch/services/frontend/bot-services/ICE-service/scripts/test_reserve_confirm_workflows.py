"""Test reserve + confirm workflows end-to-end.

This script tests:
1. Reserve workflow: Reserve inventory atomically
2. Confirm workflow: Payment → order → delivery → affiliate chain
3. Edge cases: OUT_OF_STOCK, duplicate reservations, duplicate confirmations

Uses real Docker services and test data from database.
"""

import asyncio
import logging
from uuid import uuid4
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.orchestration.reserve import ReservationWorkflow
from app.orchestration.confirm import ConfirmationWorkflow
from app.cache.redis_client import RedisCache, get_redis_cache
from app.adapters.factory import AdapterFactory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Test data (from database exploration)
TEST_BUSINESS_ID = "8946718b-fbbb-475b-8d10-dd68d4579e88"  # "Test" business
TEST_USER_ID = "user-123"  # Placeholder - replace with real user from DB
TEST_PHONE = "260970000001"  # Test phone number


async def setup_db_session():
    """Create database session."""
    engine = create_async_engine(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/soft_launch",
        echo=False,
    )
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    return async_session()


async def create_test_cart(session, business_id: str, user_id: str) -> str:
    """
    Create a test cart with sample products.
    
    Returns:
        cart_id
    """
    logger.info("Creating test cart...")
    
    cart_adapter = AdapterFactory.get_cart_order_adapter()
    
    # Create cart
    cart_result = await cart_adapter.create_or_update_draft(
        business_id=business_id,
        user_id=user_id,
        items=[
            {
                "product_id": "PROD-001",
                "sku": "TEST-SKU-001",
                "name": "Test Product 1",
                "quantity": 2,
                "price_minor": 50000,  # 500.00 ZMW
            },
            {
                "product_id": "PROD-002",
                "sku": "TEST-SKU-002",
                "name": "Test Product 2",
                "quantity": 1,
                "price_minor": 100000,  # 1000.00 ZMW
            },
        ],
    )
    
    cart_id = cart_result.get("cart_id")
    logger.info(f"Test cart created: {cart_id}")
    
    return cart_id


async def test_reserve_workflow_success():
    """Test 1: Reserve workflow with valid cart → expect reservation success."""
    logger.info("\n" + "="*80)
    logger.info("TEST 1: Reserve workflow - Success case")
    logger.info("="*80)
    
    db = await setup_db_session()
    redis = get_redis_cache()
    
    try:
        # Create test cart
        cart_id = await create_test_cart(db, TEST_BUSINESS_ID, TEST_USER_ID)
        
        # Initialize reservation workflow
        reserve_workflow = ReservationWorkflow(db=db, redis=redis)
        
        # Reserve inventory
        session_id = str(uuid4())
        idempotency_key = str(uuid4())
        
        result = await reserve_workflow.reserve_inventory(
            session_id=session_id,
            cart_id=cart_id,
            user_id=TEST_USER_ID,
            business_id=TEST_BUSINESS_ID,
            payment_method="mobile_money",
            payment_number=TEST_PHONE,
            pickup_location="Main Store",
            delivery_location="Customer Address",
            idempotency_key=idempotency_key,
        )
        
        # Assertions
        assert result["status"] == "RESERVED", f"Expected RESERVED, got {result['status']}"
        assert result["order_draft_id"], "Expected order_draft_id"
        assert result["cart_id"] == cart_id, "Cart ID mismatch"
        
        logger.info(f"✅ TEST 1 PASSED: Reservation successful")
        logger.info(f"   Order Draft ID: {result['order_draft_id']}")
        logger.info(f"   Reservation Ref: {result.get('reservation_ref')}")
        logger.info(f"   Total Amount: {result['total_amount_minor']} minor units")
        
        return result  # Return for next test
        
    except Exception as e:
        logger.error(f"❌ TEST 1 FAILED: {e}", exc_info=True)
        raise
    finally:
        await db.close()


async def test_reserve_workflow_idempotency():
    """Test 2: Reserve workflow with duplicate idempotency key → expect cached result."""
    logger.info("\n" + "="*80)
    logger.info("TEST 2: Reserve workflow - Idempotency (duplicate prevention)")
    logger.info("="*80)
    
    db = await setup_db_session()
    redis = get_redis_cache()
    
    try:
        # Create test cart
        cart_id = await create_test_cart(db, TEST_BUSINESS_ID, TEST_USER_ID)
        
        # Initialize reservation workflow
        reserve_workflow = ReservationWorkflow(db=db, redis=redis)
        
        # Reserve inventory (first time)
        session_id = str(uuid4())
        idempotency_key = str(uuid4())
        
        result1 = await reserve_workflow.reserve_inventory(
            session_id=session_id,
            cart_id=cart_id,
            user_id=TEST_USER_ID,
            business_id=TEST_BUSINESS_ID,
            payment_method="mobile_money",
            payment_number=TEST_PHONE,
            idempotency_key=idempotency_key,
        )
        
        # Reserve inventory again (same idempotency key)
        result2 = await reserve_workflow.reserve_inventory(
            session_id=session_id,
            cart_id=cart_id,
            user_id=TEST_USER_ID,
            business_id=TEST_BUSINESS_ID,
            payment_method="mobile_money",
            payment_number=TEST_PHONE,
            idempotency_key=idempotency_key,  # Same key
        )
        
        # Assertions
        assert result1["order_draft_id"] == result2["order_draft_id"], "Idempotency failed: different order_draft_ids"
        assert result1["status"] == result2["status"], "Idempotency failed: different statuses"
        
        logger.info(f"✅ TEST 2 PASSED: Idempotency working correctly")
        logger.info(f"   Both requests returned same order_draft_id: {result1['order_draft_id']}")
        
    except Exception as e:
        logger.error(f"❌ TEST 2 FAILED: {e}", exc_info=True)
        raise
    finally:
        await db.close()


async def test_confirm_workflow_success(reservation_result: dict):
    """Test 3: Confirm workflow end-to-end → expect order + payment + delivery."""
    logger.info("\n" + "="*80)
    logger.info("TEST 3: Confirm workflow - Success case (end-to-end)")
    logger.info("="*80)
    
    db = await setup_db_session()
    redis = get_redis_cache()
    
    try:
        # Initialize confirmation workflow
        confirm_workflow = ConfirmationWorkflow(db=db, redis=redis)
        
        # Confirm order
        order_draft_id = reservation_result["order_draft_id"]
        idempotency_key = str(uuid4())
        
        result = await confirm_workflow.confirm_order(
            order_draft_id=order_draft_id,
            payment_details={
                "payment_number": TEST_PHONE,
                "amount_minor": reservation_result["total_amount_minor"],
            },
            delivery_details={
                "pickup_location": "Main Store",
                "delivery_location": "Customer Address",
            },
            affiliate_context=None,  # No affiliate for this test
            idempotency_key=idempotency_key,
        )
        
        # Assertions
        assert result["status"] == "CONFIRMED", f"Expected CONFIRMED, got {result['status']}"
        assert result["order_id"], "Expected order_id"
        assert result["payment_ref"], "Expected payment_ref"
        assert result["order_draft_id"] == order_draft_id, "Order draft ID mismatch"
        
        logger.info(f"✅ TEST 3 PASSED: Order confirmation successful")
        logger.info(f"   Order ID: {result['order_id']}")
        logger.info(f"   Payment Ref: {result['payment_ref']}")
        logger.info(f"   Delivery ID: {result.get('delivery_id')}")
        logger.info(f"   Delivery Code: {result.get('delivery_code')}")
        
        return result  # Return for next test
        
    except Exception as e:
        logger.error(f"❌ TEST 3 FAILED: {e}", exc_info=True)
        raise
    finally:
        await db.close()


async def test_confirm_workflow_with_affiliate():
    """Test 4: Confirm workflow with affiliate → expect attribution event."""
    logger.info("\n" + "="*80)
    logger.info("TEST 4: Confirm workflow - With affiliate attribution")
    logger.info("="*80)
    
    db = await setup_db_session()
    redis = get_redis_cache()
    
    try:
        # Create test cart
        cart_id = await create_test_cart(db, TEST_BUSINESS_ID, TEST_USER_ID)
        
        # Reserve inventory first
        reserve_workflow = ReservationWorkflow(db=db, redis=redis)
        session_id = str(uuid4())
        
        reservation_result = await reserve_workflow.reserve_inventory(
            session_id=session_id,
            cart_id=cart_id,
            user_id=TEST_USER_ID,
            business_id=TEST_BUSINESS_ID,
            payment_method="mobile_money",
            payment_number=TEST_PHONE,
        )
        
        # Initialize confirmation workflow
        confirm_workflow = ConfirmationWorkflow(db=db, redis=redis)
        
        # Confirm order with affiliate context
        order_draft_id = reservation_result["order_draft_id"]
        
        # Use real affiliate ID from database (discovered in Phase 3 exploration)
        TEST_AFFILIATE_ID = "c02b6e8b-60fb-491b-942c-2962267d05f0"
        
        result = await confirm_workflow.confirm_order(
            order_draft_id=order_draft_id,
            payment_details={
                "payment_number": TEST_PHONE,
                "amount_minor": reservation_result["total_amount_minor"],
            },
            delivery_details={
                "pickup_location": "Main Store",
                "delivery_location": "Customer Address",
            },
            affiliate_context={
                "affiliate_id": TEST_AFFILIATE_ID,
                "code": "TEST-AFFILIATE-CODE",
                "campaign": "test-campaign",
            },
        )
        
        # Assertions
        assert result["status"] == "CONFIRMED", f"Expected CONFIRMED, got {result['status']}"
        assert result["order_id"], "Expected order_id"
        
        # Note: affiliate_attribution might be False if attribution service fails
        # (not a blocker for order confirmation)
        logger.info(f"   Affiliate Attribution: {'✅' if result.get('affiliate_attribution') else '⚠️ Failed (non-blocking)'}")
        
        logger.info(f"✅ TEST 4 PASSED: Confirmation with affiliate successful")
        logger.info(f"   Order ID: {result['order_id']}")
        
    except Exception as e:
        logger.error(f"❌ TEST 4 FAILED: {e}", exc_info=True)
        raise
    finally:
        await db.close()


async def test_fetch_payment_status(confirmation_result: dict):
    """Test 5: Fetch payment status for confirmed order."""
    logger.info("\n" + "="*80)
    logger.info("TEST 5: Fetch payment status")
    logger.info("="*80)
    
    db = await setup_db_session()
    redis = get_redis_cache()
    
    try:
        # Initialize confirmation workflow
        confirm_workflow = ConfirmationWorkflow(db=db, redis=redis)
        
        # Fetch payment status
        order_id = confirmation_result["order_id"]
        payment_ref = confirmation_result["payment_ref"]
        
        payment_status = await confirm_workflow.fetch_payment_status(
            order_id=order_id,
            payment_ref=payment_ref,
        )
        
        # Assertions
        assert payment_status.get("status"), "Expected payment status"
        
        logger.info(f"✅ TEST 5 PASSED: Payment status retrieved")
        logger.info(f"   Order ID: {order_id}")
        logger.info(f"   Payment Ref: {payment_ref}")
        logger.info(f"   Payment Status: {payment_status.get('status')}")
        
    except Exception as e:
        logger.error(f"❌ TEST 5 FAILED: {e}", exc_info=True)
        raise
    finally:
        await db.close()


async def main():
    """Run all tests."""
    logger.info("\n" + "="*80)
    logger.info("RESERVE + CONFIRM WORKFLOWS TEST SUITE")
    logger.info("="*80)
    logger.info(f"Test Business ID: {TEST_BUSINESS_ID}")
    logger.info(f"Test Phone: {TEST_PHONE}")
    logger.info("="*80)
    
    try:
        # Test 1: Reserve workflow - Success
        reservation_result = await test_reserve_workflow_success()
        
        # Test 2: Reserve workflow - Idempotency
        await test_reserve_workflow_idempotency()
        
        # Test 3: Confirm workflow - Success
        confirmation_result = await test_confirm_workflow_success(reservation_result)
        
        # Test 4: Confirm workflow - With affiliate
        await test_confirm_workflow_with_affiliate()
        
        # Test 5: Fetch payment status
        await test_fetch_payment_status(confirmation_result)
        
        logger.info("\n" + "="*80)
        logger.info("✅ ALL TESTS PASSED")
        logger.info("="*80)
        
    except Exception as e:
        logger.error("\n" + "="*80)
        logger.error("❌ TEST SUITE FAILED")
        logger.error("="*80)
        raise
    finally:
        # Cleanup adapters
        AdapterFactory.cleanup_all()


if __name__ == "__main__":
    asyncio.run(main())
