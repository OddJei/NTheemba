import os
import sys


def _add_app_path():
    here = os.path.dirname(__file__)
    app_dir = os.path.normpath(os.path.join(here, "..", "app"))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)


_add_app_path()

import runtime_engine as engine  # type: ignore


def test_validate_payment_inputs_phone_format():
    errors = engine.validate_payment_inputs(
        phone="12345",
        delivery_option="pickup",
        town=None,
        address=None,
        available_towns=None,
    )
    assert errors.get("phone") == "invalid_phone"


def test_validate_payment_inputs_delivery_option():
    errors = engine.validate_payment_inputs(
        phone="260977123456",
        delivery_option="ship",
        town=None,
        address=None,
        available_towns=None,
    )
    assert errors.get("delivery_option") == "invalid_option"


def test_validate_payment_inputs_delivery_town_and_address():
    available = [{"town_name": "Lusaka", "delivery_price": 1500}]
    errors = engine.validate_payment_inputs(
        phone="260977123456",
        delivery_option="delivery",
        town="Ndola",
        address="",
        available_towns=available,
    )
    assert errors.get("town") == "invalid_town"
    assert errors.get("address") == "invalid_address"


def test_build_payment_context_schema():
    snapshot = {"user_text": "pay", "diagnostics": {"source": "test"}, "user_state": {"stage": "payment"}}
    store_oob = {"cart": {"items": [{"product_id": "p1", "product_name": "Bread", "price": 30}]}}
    ctx = engine.build_payment_context(
        snapshot=snapshot,
        store_oob=store_oob,
        order_id="ord-1",
        payment_phone="260977123456",
        delivery_option="delivery",
        delivery_town="Lusaka",
        delivery_address="Town center",
        total_price=60,
    )
    assert ctx.get("order_id") == "ord-1"
    assert ctx.get("payment_phone") == "260977123456"
    assert ctx.get("delivery_option") == "delivery"
    assert ctx.get("delivery_location", {}).get("town") == "Lusaka"
    assert ctx.get("delivery_location", {}).get("address") == "Town center"
    assert ctx.get("payment_method") == "mobile_money"
    assert ctx.get("cart_items")
