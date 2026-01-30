import os
import json
import uuid
from redis import Redis

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
r = Redis.from_url(redis_url, decode_responses=True)

stream = "reply:requests"
payload = {
    "event_id": str(uuid.uuid4()),
    "session_id": "test-session-1",
    "text": "Hello, I'd like to confirm my order #12345. Business name: Kitwe Solar",
    "meta": {"business_name": "Kitwe Solar", "platform": "whatsapp"},
}
# publish as payload JSON string for the worker parser
entry_id = r.xadd(stream, {"payload": json.dumps(payload)})
print("Published to", stream, "id", entry_id, "event_id", payload["event_id"])