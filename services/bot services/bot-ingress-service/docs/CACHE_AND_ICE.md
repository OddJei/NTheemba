## Ingress cache schemas and ICE endpoints

This document describes the JSON shapes cached by the ingress service and the ICE endpoints the ingress calls when a cache miss occurs.

1) Bot metadata (first cache lookup)

Key pattern: `cache:bot_by_phone:{phone}`

Schema (pretty JSON):

{
  "bot_type": "default",
  "bot_details": {
    "id": "bot_def_001",
    "phone": "ntb_default",
    "display_name": "Default Store Bot",
    "default_locale": "en",
    "config_flags": {
      "accepts_orders": true,
      "supports_pickup": true,
      "supports_delivery": true
    },
    "menu_reference": "cache:catalog_snapshot:biz_321:latest",
    "schema_version": "1.0"
  },
  "business_details": {
    "id": "biz_321",
    "name": "Example MSME",
    "contact": "+254700000000",
    "delivery_areas_ref": "cache:msme_profile:biz_321",
    "supported_payment_methods": ["mpesa", "card"],
    "schema_version": "1.0"
  },
  "owner_details": {
    "owner_id": "owner_777",
    "owner_name": "Alice Admin",
    "contact": "+254700000001"
  },
  "updated_at": "2025-12-27T00:00:00Z"
}

2) User profile (next cache lookup)

Key patterns: `cache:user_by_phone:{business_id}:{phone}` or `cache:user_by_phone::{phone}`

Schema (pretty JSON):

{
  "id": "user_abc123",
  "phone": "097xxxxxxx",
  "phone_masked": "097*****xxx",
  "name": "Jane Customer",
  "roles": ["public"],
  "is_authenticated": true,
  "linked_business_id": null,
  "preferences": {
    "language": "en",
    "currency": "KES",
    "marketing_opt_in": false
  },
  "last_seen": "2025-12-27T00:05:00Z",
  "schema_version": "1.0"
}

3) Session context (later cache lookup)

Key pattern: `cache:session_context:{session_id}`

Schema (pretty JSON):

{
  "session_id": "sess_097xxxxxxx_default_bot_1766791079",
  "session_mode": "public",
  "bot_type": "default",
  "current_node": null,
  "started_at": "2025-12-27T00:00:00Z",
  "last_active_at": "2025-12-27T00:05:00Z",
  "order_draft_key": "cache:order_draft:sess_097xxxxxxx_default_bot_1766791079",
  "previous_events": [
    {
      "event_id": "req_e888a820",
      "timestamp": "2025-12-26T23:17:59.974859Z",
      "normalized_text": "hi, what can i do here?"
    }
  ],
  "expected_input": null,
  "intent_required": true,
  "schema_version": "1.0",
  "hydrated_at": "2025-12-27T00:05:01Z"
}

4) ICE endpoints called by ingress

- The ingress uses `preload_session_context(...)` in `app/clients/ice_service.py` when `cache:session_context:{session_id}` is missing.
- Configuration for the ICE base URL is `ICE_SERVICE_URL` and the preload path default is `ICE_PRELOAD_PATH` (default: `/api/v1/hydrate/session`). These are defined in `app/core/config.py` as `ice_service_url` and `ice_preload_path`.

Preload request shape (sent as JSON POST):

{
  "event_id": "<request_id>",
  "session_id": "<session_id>",
  "user_phone": "<user_phone>",
  "bot_id": "<bot_id>",
  "platform": "<platform>",
  "bot_type": "<bot_type>",
  "reason": "ingress_cache_miss",
  "required_blobs": ["session", "order_draft", "bot_meta"],
  "business_id": "<optional business_id>"
}

Expected ICE response: a JSON object (map) containing hydrated blobs the ingress can write into cache; ingress expects a dict and will store it under `cache:session_context:{session_id}`. Example returned object:

{
  "session": {
    "session_id": "sess_...",
    "session_mode": "public",
    "current_node": null,
    "started_at": "...",
    "last_active_at": "...",
    "schema_version": "1.0"
  },
  "order_draft": {
    "order_id": "ord_123",
    "items": [],
    "status": "draft",
    "updated_at": "...",
    "schema_version": "1.0"
  },
  "bot_meta": {
    "bot_type": "default",
    "bot_details": { /* .. */ }
  },
  "hydrated_at": "2025-12-27T00:05:01Z"
}

Location: `services/bot services/bot-ingress-service/docs/CACHE_AND_ICE.md`
