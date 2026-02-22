import asyncio
import json
import os
import sys
import urllib.request

# Make repo root and ICE app importable
cur = os.path.abspath(os.path.dirname(__file__))
root = cur
while not os.path.isdir(os.path.join(root, "libs")):
    parent = os.path.abspath(os.path.join(root, ".."))
    if parent == root:
        break
    root = parent
if root not in sys.path:
    sys.path.insert(0, root)
ice_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ice_root not in sys.path:
    sys.path.insert(0, ice_root)

from app.blob_builders import build_business_blob

MSME_BASE = os.environ.get('MSME_BASE', 'http://localhost:8500')
INTERNAL_SECRET = os.environ.get('X_INTERNAL_SECRET', '0a1b2c3d-4e5f-6789-abcd-ef0123456789')


def fetch_businesses():
    url = f"{MSME_BASE}/internal/businesses"
    req = urllib.request.Request(url, headers={
        'Accept': 'application/json',
        'X-Internal-Secret': INTERNAL_SECRET,
    })
    with urllib.request.urlopen(req, timeout=10) as r:
        body = r.read().decode()
        parsed = json.loads(body)
        if isinstance(parsed, dict):
            return parsed.get('value') or []
        if isinstance(parsed, list):
            return parsed
        return []


async def main():
    print('Fetching businesses from', MSME_BASE)
    try:
        businesses = fetch_businesses()
    except Exception as e:
        print('Failed to fetch businesses:', e)
        return

    if not businesses:
        print('No businesses returned')
        return

    first = businesses[0]
    biz_id = first.get('id') or first.get('business_id')
    print('Using business id:', biz_id)

    blob = await build_business_blob(business_id=biz_id, session_id='live-fetch')
    print(json.dumps(blob, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
