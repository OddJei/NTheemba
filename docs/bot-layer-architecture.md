# NTheemba Bot Layer Architecture (Top-Level)

## Goal
Deliver a fast, modular, queue-driven bot system where the **bot layer uses Redis as the primary state/cache**, and calls backend services **through ICE** only when needed (cache miss, validation, or commit operations).

## Core Components
- **Channel Gateways**: WhatsApp / SMS / Web entrypoints.
- **Ingress Service**: normalizes inbound messages, resolves sessions, hydrates context (cache-first), and publishes into the bot pipeline.
- **Intent Service (optional)**: resolves intent/entities only when a message requires classification.
- **Bot Services**:
  - **Custom Bot Service**: customer flows (orders, checkout), builds/updates the Order Object.
  - **Default Bot Service**: MSME/utility flows (onboarding, analytics, generic help).
- **Reply Service (optional)**: templates/rendering and channel-aware formatting when the bot requests it.
- **Outbound Service**: sends outbound messages to gateways and manages delivery/session finalization.
- **ICE Service**: backend abstraction for authoritative reads and all commits to downstream API services.
- **Redis**: queue transport + cache/state store.

## Reduced E2E Payload Flow (4 Queues)
The architecture is reduced to **4 queues**, with **Intent** and **Reply** invoked only when needed.

### Queue 1 — `inbound_message`
- Producer: Channel gateway
- Consumer: Ingress
- Purpose: raw inbound event

### Queue 2 — `resolvedpayload`
- Producer: Ingress
- Consumer: Intent Service (only when required) **or** routed onward
- Purpose: normalized + session-resolved payload (cache-first)

### Queue 3 — `custom/default bot queue`
- Producer: Ingress (bypass) or Intent Service (intent-mode)
- Consumer: Custom Bot Service / Default Bot Service
- Purpose: execute journey (tree), update state, decide reply

### Queue 4 — `outbound_message`
- Producer: Bot Service
- Consumer: Outbound Service
- Purpose: final outbound dispatch + delivery tracking + session closure rules

## When Intent Service Is Used
Ingress (or Bot, if you choose bot-owned routing) decides whether intent resolution is required.

Use Intent when:
- Session has no active journey context (new/unknown node)
- Node expects open-ended text (“what do you want?”)
- Message is ambiguous and routing isn’t deterministic
- You need global shortcuts (help/back/restart) normalized consistently

Bypass Intent when:
- Current node expects deterministic input (quantity, phone, confirm, selection)
- Message comes from explicit UI/action payload (button/menu choice)

## When Reply Service Is Used
Reply is a helper the bot calls only when needed.

Use Reply when:
- Output needs templates, localization, or consistent phrasing
- Output needs channel-aware formatting (buttons/lists/cards)

Bypass Reply when:
- Bot already produces final plain text suitable for the channel

## Cache-First Rules
### Redis is primary for:
- Session state (session_id, mode, last node, reset flags, throttling)
- Order Object state (cart, fulfillment, payment status) for Custom Bot
- Lightweight context snapshots (MSME profile, delivery areas, payment methods) with TTL

### ICE is used for:
- Cache miss hydration (first session, expired keys)
- Authoritative validation (stock, pricing, payment verification)
- Commit operations (place order, payment initiation/confirmation, final order state)

## Session Lifecycle
- `active`: messages continue within session timeout
- `finished`: payment success / order finished
- `cancelled`: user cancels / payment fails and cancels
- `inactive`: outbound finalization or timeout

## Payload Contract (Envelope)
All internal queues should carry a consistent envelope for traceability:
- `event_id` (unique per inbound)
- `session_id`
- `channel`, `from`, `to`
- `timestamp`
- `message` (text + attachments)
- `context` (cache-first snapshot)
- `routing` (bot_type, intent_required, reply_required)
- `intent` (optional; added by Intent Service)
- `bot_result` (optional; added by Bot Service)
- `outbound` (final outbound form)

## Service Ownership Boundaries
- Ingress: normalize + session resolution + cache hydrate + routing decision
- Intent: intent/entities only
- Bot: journey/tree execution + state mutation + calls ICE when needed
- Reply: rendering/templating only
- Outbound: delivery + session finalization
- ICE: all backend reads/writes behind stable JSON contracts

## Open Decisions (to finalize early)
- Who owns intent routing decision? (recommended: Ingress based on session state)
- Redis key naming and TTL policy per domain (session/order/context)
- Idempotency strategy across queues (event_id/request_id)
