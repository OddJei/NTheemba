Order-Delivery Refactor Checklist
=================================

Purpose
-------

Remove synchronous affiliate dispatches and consume affiliate-attribution events from Outbox; ensure idempotent handling of delivery and payout flows.

Checklist
---------

- [ ] 1) Identify synchronous affiliate calls and mark for removal
  - Find places that POST to Affiliate-Engine directly during order events.

- [ ] 2) Add Outbox consumer integration
  - Accept Outbox-dispatched `msme.subscription.payment_succeeded` and other affinity events.

- [ ] 3) Ensure idempotent state changes on delivery/payout
  - Protect financial writes with idempotency keys and DB constraints.

Clarifying questions
--------------------

1) List the current synchronous affiliate endpoints that Order-Delivery calls (I can scan the code if helpful).
scan the code
2) Should Order-Delivery expose a `POST /events/outbox` consumer endpoint or rely on the central OutboxDispatcher to call its business endpoints?
answer:rely on the central outbox