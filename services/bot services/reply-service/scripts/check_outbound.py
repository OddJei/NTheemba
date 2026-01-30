import os
import json
from redis import Redis

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
r = Redis.from_url(redis_url, decode_responses=True)

stream = "outbound:requests"
items = r.xrevrange(stream, count=5)
if not items:
    print("No items in", stream)
else:
    for message_id, data in items:
        print("--- id:", message_id)
        try:
            payload = data.get("payload")
            if payload and isinstance(payload, str):
                parsed = json.loads(payload)
                print(json.dumps(parsed, indent=2))
            else:
                print(data)
        except Exception as e:
            print("error reading message:", e)
