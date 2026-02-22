import pytest

from app.helpers.service_helpers import select_delivery_location
from app.adapters.msme import MsmeEngineAdapter


class DummyAdapter:
    def __init__(self, locations):
        self._locations = locations

    async def fetch_business_delivery_locations(self, business_id):
        return self._locations


@pytest.mark.asyncio
async def test_select_delivery_location_match_name(monkeypatch):
    locations = [{"id": "l1", "name": "Lusaka", "price_minor": 2500}]
    monkeypatch.setattr('app.helpers.service_helpers.AdapterFactory.get_msme_adapter', lambda: DummyAdapter(locations))

    res = await select_delivery_location("b1", "Lusaka")
    assert res is not None
    assert res["name"] == "Lusaka"


@pytest.mark.asyncio
async def test_select_delivery_location_no_match(monkeypatch):
    locations = [{"id": "l1", "name": "Lusaka", "price_minor": 2500}]
    monkeypatch.setattr('app.helpers.service_helpers.AdapterFactory.get_msme_adapter', lambda: DummyAdapter(locations))

    res = await select_delivery_location("b1", "Kitwe")
    assert res is None
