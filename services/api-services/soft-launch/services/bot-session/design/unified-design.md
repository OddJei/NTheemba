# Unified Bot-Session (Soft Launch)

This soft-launch service merges:
- User-Bot Session lifecycle (sessions)
- User-Bot Event trail (events)

Goal: one consistent entrypoint for WhatsApp/SMS payload handling:
1) resolve/create session
2) create an event record (audit + replay context)
3) route downstream calls (Cart/Order/Payment/Notification/Delivery)
4) update the event as actions occur

## A) Session Model (from user-bot-session-service)

Table: user_bot_session_service.sessions
- id: UUID (PK)
- user_id: UUID (nullable for anonymous)
- user_phone: TEXT (indexed)
- bot_id: UUID
- business_id: UUID (nullable; use business_id consistently in soft-launch)
- bot_type: ENUM('default', 'custom')
- session_mode: ENUM('public', 'registered', 'customer', 'staff')
- platform: TEXT ('wa' | 'sms' | 'web')
- current_node: TEXT
- last_event_id: UUID (nullable)
- object_context: JSONB (nullable)
- status: ENUM('active','inactive') NOT NULL DEFAULT 'active'
- created_at: TIMESTAMP
- updated_at: TIMESTAMP

Constraints:
- UNIQUE(user_phone, bot_id, platform)

Routes:
- POST /session/create
- GET  /session/{session_id}
- GET  /session/resolve?user_phone=...&bot_id=...&platform=...
- GET  /session/by-phone-platform/{user_phone}/{platform}

## B) Event Model (from user-bot-event-service)

Table: user_bot_event_service.events
- id: UUID (PK)
- session_id: UUID (FK → user_bot_session_service.sessions.id)
- user_phone: TEXT (indexed, nullable)
- user_id: UUID (nullable)
- bot_id: UUID
- last_event_id: UUID (nullable)
- message_count: INTEGER
- event_type: TEXT
- payload_events: JSONB
- previous_turns: JSONB (nullable)
- status: TEXT
- updated_fields: JSONB (nullable)
- created_at: TIMESTAMP
- updated_at: TIMESTAMP

Routes:
- POST /event/create
- PUT  /event/{id}/update
- GET  /event/{id}
- GET  /event/session/{session_id}
- GET  /event/phone/{user_phone}

## C) Integration touchpoints (Soft Launch)

Inbound (WhatsApp/SMS):
- Bot ingress posts payload to Bot-Session
- Bot-Session:
  - resolves session (Auth service role lookup when needed)
  - creates an event (event_type='message', status='created')
  - enriches payload with session_id, last_event_id, platform, business_id

Downstream orchestration (typical commerce flow):
- Cart:
  - create/update cart for session_id
  - checkout emits cart_checked_out
- Order:
  - create order from cart + delivery details
  - status transitions: pending -> confirmed -> paid -> fulfilled/cancelled
- Payment + Revenue:
  - initiate payment, verify (PawaPay sandbox)
  - emits payment_success/payment_failed
- Delivery:
  - on payment_success generate delivery code, confirm by code
  - emits delivery_confirmed
- Notification:
  - on order_created/order_paid/delivery_code_generated send MSME + customer messages

Event update rule:
- Every downstream milestone updates the originating event via PUT /event/{id}/update
  (append into payload_events.events[], and update status)
