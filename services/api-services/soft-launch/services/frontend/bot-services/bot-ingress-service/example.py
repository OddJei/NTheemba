import asyncio
import aioredis
import aiohttp
from pydantic import BaseModel, ValidationError, validator
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

# Constants
MIN_INTENT_CONF = 0.7
SESSION_TIMEOUT_SECONDS = 1800

# Redis keys templates
SESSION_KEY = "session:{}"
INTENT_TREE_KEY = "intent_tree:{}"
NODE_STATE_KEY = "node_state:{}"

# Redis streams
INCOMING_MESSAGES_STREAM = "incoming_messages"
RESOLVED_PAYLOAD_DEFAULT_STREAM = "resolved_payload_default"
RESOLVED_PAYLOAD_CUSTOM_STREAM = "resolved_payload_custom"

# HTTP endpoints (example base URLs)
BOT_SERVICE_URL = "http://localhost:8000"
AUTH_SERVICE_URL = "http://localhost:8001"
CAPABILITY_SERVICE_URL = "http://localhost:8002"
SESSION_SERVICE_URL = "http://localhost:8003"

class InboundPayload(BaseModel):
    request_id: str
    message: Optional[str]
    attachments: Optional[List[Any]] = []
    to: str
    from_: str  # renamed from 'from' because it is a reserved word
    timestamp: datetime
    meta: Dict[str, Any]

    @validator('meta')
    def validate_meta(cls, v):
        if 'platform' not in v or v['platform'] not in {"wa", "sms"}:
            raise ValueError("meta.platform must be 'wa' or 'sms'")
        return v

    class Config:
        fields = {'from_': 'from'}

async def fetch_json(session: aiohttp.ClientSession, url: str, params=None):
    async with session.get(url, params=params) as resp:
        resp.raise_for_status()
        return await resp.json()

async def post_json(session: aiohttp.ClientSession, url: str, json_data=None):
    async with session.post(url, json=json_data) as resp:
        resp.raise_for_status()
        return await resp.json()

def normalize_text(text: str) -> str:
    return text.lower().strip() if text else ""

async def get_bot_by_phone(session: aiohttp.ClientSession, phone: str):
    url = f"{BOT_SERVICE_URL}/bot/by-phone/{phone}"
    try:
        return await fetch_json(session, url)
    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            # Could implement bot creation logic here if allowed
            return None
        raise

async def lookup_user(session: aiohttp.ClientSession, phone: str, business_id: Optional[str] = None):
    params = {"phone": phone}
    if business_id:
        params["business_id"] = business_id
    url = f"{AUTH_SERVICE_URL}/auth/users/lookup"
    try:
        return await fetch_json(session, url, params=params)
    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            return None
        raise

async def fetch_capabilities(session: aiohttp.ClientSession, mode_name: str):
    url = f"{CAPABILITY_SERVICE_URL}/capabilities/by-mode-name/{mode_name}"
    return await fetch_json(session, url)

async def get_or_create_session(redis, user_phone: str, bot_id: str, platform: str):
    uniqueness_key = f"{user_phone}:{bot_id}:{platform}"
    # Stored sessions indexed by this uniqueness key; for simplicity, store session_id in a Redis hash
    session_id_key = f"session_id_by_key:{uniqueness_key}"
    session_id = await redis.get(session_id_key)
    now = datetime.now(timezone.utc).isoformat()
    if session_id:
        session_key = SESSION_KEY.format(session_id.decode())
        session_data = await redis.hgetall(session_key)
        if not session_data:
            # Session data missing, create new
            session_id = None
        else:
            status = session_data.get(b'status', b'').decode()
            last_active_at = session_data.get(b'last_active_at', b'').decode()
            if status != "active" or (last_active_at and (datetime.now(timezone.utc) - datetime.fromisoformat(last_active_at)).total_seconds() > SESSION_TIMEOUT_SECONDS):
                # Reactivate session
                await redis.hset(session_key, mapping={
                    "status": "active",
                    "last_active_at": now,
                })
                return session_id.decode(), True
            else:
                # Reuse active session
                return session_id.decode(), False

    if not session_id:
        # Create new session
        session_id = f"sess_{user_phone}_{bot_id}_{int(datetime.now().timestamp())}"
        session_key = SESSION_KEY.format(session_id)
        await redis.hset(session_key, mapping={
            "status": "active",
            "started_at": now,
            "last_active_at": now,
            "user_phone": user_phone,
            "bot_id": bot_id,
            "platform": platform,
        })
        await redis.set(session_id_key, session_id)
        return session_id, False

async def process_message(redis, session_http, raw_data):
    try:
        payload = InboundPayload(**raw_data)
    except ValidationError as e:
        print(f"Payload validation error: {e}")
        return

    # Idempotency check (skip if request_id processed)
    idempotency_key = f"idempotency:{payload.request_id}"
    if await redis.exists(idempotency_key):
        print(f"Duplicate request_id {payload.request_id}, skipping")
        return
    else:
        await redis.set(idempotency_key, "1", expire=3600)  # expire in 1 hour

    # Resolve bot by to (bot phone)
    bot_info = await get_bot_by_phone(session_http, payload.to)
    if not bot_info:
        print(f"Bot not found or creation not allowed for phone: {payload.to}")
        return

    bot_type = bot_info.get("bot_type", "default")
    business_details = bot_info.get("business_details", {})
    bot_details = bot_info.get("bot_details", {})
    owner_details = bot_info.get("owner_details", {})

    # Resolve user and session_mode
    if bot_type == "custom":
        business_id = business_details.get("id")
        user_info = await lookup_user(session_http, payload.from_, business_id)
        roles = user_info.get("roles", []) if user_info else []
        if "staff" in roles:
            session_mode = "staff"
        else:
            session_mode = "customer"
        user_enrich = {
            "id": user_info.get("id") if user_info else None,
            "phone": payload.from_,
            "roles": roles if roles else ["customer"],
            "authenticated": bool(user_info),
            "business_id": business_id,
            "locale": user_info.get("locale") if user_info else "en",
        }
    else:  # default bot
        user_info = await lookup_user(session_http, payload.from_)
        roles = user_info.get("roles", []) if user_info else []
        if set(roles).intersection({"msme", "affiliate"}):
            session_mode = "registered"
        else:
            session_mode = "public"
        user_enrich = {
            "id": user_info.get("id") if user_info else None,
            "phone": payload.from_,
            "roles": roles if roles else ["public"],
            "authenticated": bool(user_info),
            "locale": user_info.get("locale") if user_info else "en",
        }

    # Resolve capabilities for session_mode
    mode_name_map = {
        "public": "public",
        "registered": "registered_user",
        "customer": "customer",
        "staff": "staff_only",
    }
    capabilities_resp = await fetch_capabilities(session_http, mode_name_map.get(session_mode, "public"))
    capabilities = capabilities_resp.get("capabilities", [])
    allowed_actions = [c.get("action") for c in capabilities if "action" in c]

    # Manage session
    session_id, reactivated = await get_or_create_session(redis, payload.from_, bot_details.get("id", "default_bot"), payload.meta["platform"])

    # Normalize text
    normalized_text = normalize_text(payload.message)

    now_iso = datetime.now(timezone.utc).isoformat()

    # Build enriched payload
    enriched_payload = {
        "request_id": payload.request_id,
        "event_id": None,
        "message": payload.message,
        "to": payload.to,
        "from": payload.from_,
        "timestamp": payload.timestamp.isoformat(),
        "meta": {
            "platform": payload.meta["platform"],
            "bot": {
                "bot_details": bot_details,
                "business_details": business_details,
                "owner_details": owner_details,
            },
            "user": user_enrich,
            "session": {
                "session_id": session_id,
                "session_mode": session_mode,
                "bot_type": bot_type,
                "current_node": None,
                "started_at": now_iso,
                "last_active_at": now_iso,
                "reset_requested": False,
            },
            "previous_events": [],  # For simplicity, empty
            "session_event": {
                "event_id": None,
                "started_at": now_iso,
                "ingress": {
                    "normalized_text": normalized_text,
                    "attachments": payload.attachments,
                    "capabilities": ["text"],  # simplified; could be enriched
                    "allowed_actions": allowed_actions,
                    "mode": session_mode,
                    "mode_id": mode_name_map.get(session_mode, "public"),
                    "received_at": now_iso,
                    "user_session": {
                        "session_id": session_id,
                        "started_at": now_iso,
                        "last_active_at": now_iso,
                    },
                    "previous_events_count": 0,
                }
            }
        }
    }

    # Publish to resolved_payload stream based on bot_type
    stream_name = RESOLVED_PAYLOAD_CUSTOM_STREAM if bot_type == "custom" else RESOLVED_PAYLOAD_DEFAULT_STREAM
    await redis.xadd(stream_name, {"payload": str(enriched_payload)})

    print(f"Processed message {payload.request_id} published to {stream_name}")

async def main():
    redis = await aioredis.from_url("redis://localhost", decode_responses=True)
    async with aiohttp.ClientSession() as session_http:
        last_id = "0-0"
        while True:
            # Read new messages from incoming_messages stream
            resp = await redis.xread({INCOMING_MESSAGES_STREAM: last_id}, count=10, block=1000)
            if not resp:
                continue
            for stream, messages in resp:
                for message_id, message_data in messages:
                    last_id = message_id
                    raw_payload_str = message_data.get("payload") or message_data.get("message") or "{}"
                    try:
                        # Assuming payload is sent as JSON string
                        import json
                        raw_payload = json.loads(raw_payload_str)
                    except Exception as e:
                        print(f"Failed to parse payload JSON: {e}")
                        continue
                    await process_message(redis, session_http, raw_payload)

if __name__ == "__main__":
    asyncio.run(main())