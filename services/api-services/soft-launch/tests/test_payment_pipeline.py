import pytest
import sys
import os


def _add_import_path():
    root = os.getcwd()
    svc = os.path.join(root, "services", "frontend", "bot-services", "custom-bot-service")
    if svc not in sys.path:
        sys.path.insert(0, svc)


_add_import_path()

from app import runtime_engine as re


def test_phone_validation():
    assert re._validate_phone("260971234567")
    assert not re._validate_phone("0971234567")
    assert not re._validate_phone("+260971234")


def test_delivery_option_validation():
    assert re._validate_delivery_option("pickup")
    assert re._validate_delivery_option("delivery")
    assert not re._validate_delivery_option("dropoff")


def test_validate_payment_inputs_town_check():
    towns = [{"town_name": "Lusaka", "delivery_price": 10}, {"town_name": "Ndola", "delivery_price": 20}]
    errors = re.validate_payment_inputs(phone="260971234567", delivery_option="delivery", town="Lusaka", available_towns=towns)
    assert errors == {}
    errors2 = re.validate_payment_inputs(phone="260971234567", delivery_option="delivery", town="UnknownTown", available_towns=towns)
    assert errors2.get("town") == "invalid_town"


def test_collect_payment_inputs_one_turn_simple(monkeypatch):
    payload = {"text": "260971234567 delivery Lusaka 123 Main St"}
    towns = [{"town_name": "Lusaka", "delivery_price": 10}]
    results = pytest.run = None
    import asyncio
    res = asyncio.run(re.collect_payment_inputs_one_turn(payload=payload, available_towns=towns))
    assert res.get("phone") == "260971234567"
    assert res.get("delivery_option") == "delivery"
    assert res.get("town") == "Lusaka"
