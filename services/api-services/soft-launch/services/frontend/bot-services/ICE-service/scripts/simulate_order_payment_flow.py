"""Integration simulation for order + payment confirmation.

Requires order-delivery and payment-revenue running (Docker).
Uses dummy auth token to bypass JWT in local integration tests.
"""

import asyncio
import logging
from pprint import pprint

from app.adapters.factory import AdapterFactory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    cart_order_adapter = AdapterFactory.get_cart_order_adapter()

    payload = {
        "session_id": "sess-ice-001",
        "user_phone": "260701234567",
        "business_id": "BIZ-001",
        "delivery_method": "deliver_to_customer",
        "pickup_location": "Warehouse A",
        "delivery_location": "Plot 12, Lusaka",
        "total_amount": 12500,
        "currency": "ZMW",
        "payment_number": "260701234567",
        "payment_provider": "MTN_MOMO_ZMB",
        "idempotency_key": "idem-order-001",
        "auth_token": "dummy-token",
        "role": "admin",
    }

    logger.info("Creating order + initiating payment with Order-Delivery service")
    result = await cart_order_adapter.confirm_order(payload)

    pprint(result)

    await AdapterFactory.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
