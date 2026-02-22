import asyncio
import os
import sys
import json

# Ensure the repository root (contains `libs/`) is importable so helpers can import `libs.*`
cur = os.path.abspath(os.path.dirname(__file__))
root = cur
while not os.path.isdir(os.path.join(root, "libs")):
    parent = os.path.abspath(os.path.join(root, ".."))
    if parent == root:
        break
    root = parent
if root not in sys.path:
    sys.path.insert(0, root)
# Also ensure the ICE-service app package is importable (this dir's parent)
ice_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ice_root not in sys.path:
    sys.path.insert(0, ice_root)

from app.blob_builders import build_customer_blob
from app.helpers import service_helpers


async def fake_get_user_by_phone(phone: str):
    return {}


async def fake_ensure_user_exists(phone: str, *, display_name: str = None):
    return {"id": "newuser1", "phone": phone, "name": display_name or "unknown", "role": "customer", "created_placeholder": True}


service_helpers.get_user_by_phone = fake_get_user_by_phone
service_helpers.ensure_user_exists = fake_ensure_user_exists


async def main():
    res = await build_customer_blob(phone="+260900000002", session_id=None)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
