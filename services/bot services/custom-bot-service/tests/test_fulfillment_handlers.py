import pytest

from app.handlers.fulfillment_select_delivery_option import select_delivery_option
from app.handlers.fulfillment_choose_location import choose_location


class DummyStore:
    def __init__(self, oob):
        self._oob = oob

    async def create_default_if_missing(self, session_id):
        return self._oob, 1

    async def cas_update(self, session_id, updater):
        new = updater(self._oob)
        self._oob = new
        return self._oob, 2


@pytest.mark.asyncio
async def test_select_delivery_option_sets_type_and_details():
    oob = {"cart": {"items": []}, "meta": {}}
    store = DummyStore(oob)
    res_oob, ver = await select_delivery_option(store=store, session_id="s1", method="delivery", details={"window": "ASAP"})
    assert res_oob.get("fulfillment", {}).get("type") == "delivery"
    assert res_oob.get("fulfillment", {}).get("details", {}).get("window") == "ASAP"


@pytest.mark.asyncio
async def test_choose_location_sets_address_and_pickup():
    oob = {"cart": {"items": []}, "meta": {}}
    store = DummyStore(oob)
    addr = {"line1": "123 River St", "city": "Lusaka"}
    pickup = {"id": "store_1", "name": "Main Store"}
    res_oob, ver = await choose_location(store=store, session_id="s1", address=addr, pickup_location=pickup)
    assert res_oob.get("delivery", {}).get("address", {}).get("city") == "Lusaka"
    assert res_oob.get("meta", {}).get("pickup_location", {}).get("id") == "store_1"
