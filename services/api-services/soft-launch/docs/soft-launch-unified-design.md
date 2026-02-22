# Soft Launch Unified Design (Bundle)

This doc harmonizes the soft-launch workflow across:
Cart, Order, Affiliate Engine, MSME Engine, Bot-Session, Payment+Revenue, Notification, Delivery.

## Automated pipeline summary (only manual step: physical handover)

- Bot-Session: session resolve + event logging for inbound payloads
- Cart: selection + checkout
- Order: creation + lifecycle state
- Payment+Revenue: initiate + verify + compute earnings
- Notification: MSME/customer notifications
- Delivery: delivery code + confirmation
- Affiliate Engine: attribution + earnings inputs
- MSME Engine: onboarding + business profile

## Integration rule

- All service-to-service calls/events MUST carry:
  - business_id, user_phone, session_id (when bot-originated), and correlation id (request_id)
- Payment and delivery callbacks MUST be idempotent.

See contracts/:

- db-conventions.md
- integration-points.md
- events-catalog.yaml
- status-mapping.md
