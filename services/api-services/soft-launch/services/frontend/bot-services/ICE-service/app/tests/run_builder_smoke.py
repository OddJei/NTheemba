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

from app.blob_builders import build_business_blob
from app.helpers import service_helpers


async def fake_get_business_by_id(business_id: str):
    return {"profile": {"id": business_id, "owner_phone": "+260900000001"}, "policies": {"p": True}}


async def fake_get_business_by_phone(phone: str):
    return {"id": "biz_by_phone", "name": "BizCo", "owner_phone": phone}


async def fake_get_user_by_phone(phone: str):
    return {"id": "user1", "phone": phone, "name": "Owner"}


async def fake_get_service_token(business_id: str):
    return "svc-token-xyz"


service_helpers.get_business_by_id = fake_get_business_by_id
service_helpers.get_business_by_phone = fake_get_business_by_phone
service_helpers.get_user_by_phone = fake_get_user_by_phone
service_helpers.get_service_token = fake_get_service_token


async def main():
    res = await build_business_blob(phone="+260900000001", business_id="biz1", session_id="sess1")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
