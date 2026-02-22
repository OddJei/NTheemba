import asyncio
import os
import sys
import json

# Ensure repo root and ICE-service app package are importable
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

print("RUNNER_START")


async def main():
    # Try by business_id first, then fallback to phone
    res = await build_business_blob(business_id="biz-test-001", phone="+260900000001", session_id="live-smoke")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
