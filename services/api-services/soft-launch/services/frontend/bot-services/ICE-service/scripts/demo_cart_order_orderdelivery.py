"""Demo to exercise cart + order + delivery helpers/adapters.

Usage:
    DEMO_BOT_SESSION_TOKEN=<token> DEMO_BUSINESS_ID=biz-demo python scripts/demo_cart_order_orderdelivery.py

Requires local services (bot-session, cart, order-delivery) or file-backed adapters.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path
from uuid import uuid4

# Ensure package imports resolve
ICE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ICE_DIR))
sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("demo_cart_order_delivery")

try:
    from app.helpers import service_helpers
    from app.adapters.factory import AdapterFactory
except Exception:
    logger.exception("failed to import project modules; ensure sys.path is correct")
    raise


async def main():
    token = os.getenv("DEMO_BOT_SESSION_TOKEN")
    business_id = os.getenv("DEMO_BUSINESS_ID", "biz-demo")
    auth_headers = {"Authorization": f"Bearer {token}"} if token else None

    user_phone = os.getenv("DEMO_USER_PHONE", "+260772000010")
    session_id = f"sess-{uuid4().hex[:8]}"

    logger.info("Creating cart draft for session=%s user=%s", session_id, user_phone)
    draft = await service_helpers.create_cart_draft(session_id, user_phone, business_id, idempotency_key=f"create-{uuid4().hex}", auth_headers=auth_headers)
    logger.info("draft -> %s", draft)

    # Determine draft id
    cart_id = draft.get("draft_id") or draft.get("id") or draft.get("draft_id")
    if not cart_id and isinstance(draft, dict) and draft.get("status") == "FAILED":
        logger.error("Could not create draft: %s", draft)
        return

    # Add sample items
    items = [
        {"product_id": "sku-ice-001", "qty": 2, "price_minor": 500},
        {"product_id": "sku-ice-002", "qty": 1, "price_minor": 1200},
    ]
    logger.info("Adding items to cart %s", cart_id)
    added = await service_helpers.add_cart_items(cart_id, items, idempotency_key=f"add-{uuid4().hex}", auth_headers=auth_headers)
    logger.info("add_cart_items -> %s", added)

    # Fetch carts for session
    carts = await service_helpers.get_carts_by_session(session_id)
    logger.info("carts for session %s -> %s", session_id, carts)

    # Reserve / checkout
    logger.info("Reserving items (checkout) for cart %s", cart_id)
    reserve = await service_helpers.checkout_cart(cart_id, idempotency_key=f"reserve-{uuid4().hex}")
    logger.info("reserve -> %s", reserve)

    # Confirm order via CartOrder adapter which will call Order-Delivery and Payment services
    adapter = AdapterFactory.get_cart_order_adapter()
    confirm_payload = {
        "draft_id": cart_id,
        "payment_number": user_phone,
        "business_id": business_id,
        "currency": "ZMW",
        "payment_provider": "pawapay",
        "idempotency_key": f"confirm-{uuid4().hex}",
    }
    # include auth token for order-delivery calls if available
    if token:
        confirm_payload["auth_token"] = token

    logger.info("Confirming order via adapter.confirm_order for cart %s", cart_id)
    result = await adapter.confirm_order(confirm_payload)
    logger.info("confirm_order -> %s", result)

    order_id = None
    if isinstance(result, dict):
        # adapter.confirm_order returns order/payment info for file-backed; check common keys
        order = result.get("order") or result.get("order_id") or result.get("id")
        if isinstance(order, dict):
            order_id = order.get("id") or order.get("order_id")
        elif isinstance(order, str):
            order_id = order
        # file-backed may return "order_id" top-level
        if not order_id:
            order_id = result.get("order_id") or result.get("order", {}).get("id")

    if order_id:
        logger.info("Order created: %s", order_id)
        # Initiate delivery using delivery adapter
        delivery_adapter = AdapterFactory.get_delivery_adapter()
        delivery_payload = {"order_id": order_id, "idempotency_key": f"deliv-{uuid4().hex}"}
        if token:
            delivery_payload["auth_token"] = token
        logger.info("Initiating delivery for order %s", order_id)
        deliver_resp = await delivery_adapter.create_delivery_task(delivery_payload)
        logger.info("delivery initiate -> %s", deliver_resp)

        # Confirm delivery by code if available
        delivery = deliver_resp.get("delivery") if isinstance(deliver_resp, dict) else None
        delivery_code = deliver_resp.get("delivery_code") if isinstance(deliver_resp, dict) else None
        delivery_id = delivery.get("id") if isinstance(delivery, dict) else None
        if delivery_id and delivery_code:
            logger.info("Confirming delivery id=%s with code=%s", delivery_id, delivery_code)
            confirm = await service_helpers.confirm_delivery(delivery_id, delivery_code, confirmed_by=user_phone, auth_headers=auth_headers)
            logger.info("confirm_delivery -> %s", confirm)
        else:
            logger.warning("No delivery id/code returned; skip confirm")
    else:
        logger.warning("No order id returned from confirm_order; skipping delivery flow")


if __name__ == "__main__":
    asyncio.run(main())
