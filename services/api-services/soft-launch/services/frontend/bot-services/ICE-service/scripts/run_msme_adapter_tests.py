import asyncio
import sys
from pathlib import Path
# Ensure repo app package is importable when run from scripts dir
ROOT = Path(__file__).resolve().parents[2] / "app"
sys.path.insert(0, str(ROOT))
from app.adapters.msme import MsmeEngineAdapter

class DummyResp:
    def __init__(self, status, payload):
        self.status = status
        self._payload = payload

    async def json(self):
        return self._payload

class DummySession:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, *args, **kwargs):
        return self._resp

async def run():
    payload = {"Lusaka": {"price_minor": 2500}, "Kitwe": {"price_minor": 1800}}
    resp = DummyResp(200, payload)
    adapter = MsmeEngineAdapter(base_url="http://msme")
    adapter._get_session = lambda: DummySession(resp)
    res = await adapter.fetch_business_delivery_locations("b1")
    print('res:', res)

    payload2 = [{"id": "loc1", "name": "Kitwe", "price_minor": 1800}]
    resp2 = DummyResp(200, payload2)
    adapter2 = MsmeEngineAdapter(base_url="http://msme")
    adapter2._get_session = lambda: DummySession(resp2)
    res2 = await adapter2.fetch_business_delivery_locations("b2")
    print('res2:', res2)

if __name__ == '__main__':
    asyncio.run(run())
