Affiliate-Engine Refactor Checklist
=================================

Purpose
-------
Prepare `affiliate-engine` to consume Outbox events from MSME and to maintain canonical affiliate records linked to MSME users.

Checklist
---------
- [ ] 1) Add Outbox consumer endpoint for `msme.subscription.payment_succeeded`
  - Define payload contract and required auth header (internal secret).

- [ ] 2) Ensure canonical affiliate model and sync APIs
  - Provide API to create/find affiliates by external id and to link MSME users.
  - Expose `GET /affiliates/{id}` and `POST /affiliates/link` for linking.

- [ ] 3) Support idempotent event processing
  - Ensure handling duplicate events is safe; dedupe by `event_id`.

- [ ] 4) Provide local DB FK or mapping to MSME user records
  - Decide whether MSME will store `affiliate_id` as FK / cross-repo mapping table.

Clarifying questions
--------------------
1) Do you want `affiliate-engine` to expose a simple link API used by MSME (`POST /affiliates/link`) or should MSME write the affiliate id locally and rely on affiliate-engine for eventual consistency?
answer: MSME should write the affiliate id locally in its own database and include it in the payload of the Outbox event. This allows MSME to maintain its own state and ensures that the affiliate information is available immediately for any logic that needs it within MSME. The `affiliate-engine` can then consume the Outbox event and update its own records accordingly, ensuring eventual consistency without requiring synchronous API calls between the services.
2) Which header name should dispatcher use for internal auth (suggest `X-Internal-Secret`)?
answer: Yes, the header name `X-Internal-Secret` is a good choice for internal authentication when the Outbox dispatcher posts events to `affiliate-engine` and other internal services. This header will contain a shared secret that both the dispatcher and the target service recognize for verifying the authenticity of incoming requests. Make sure to store this secret securely and rotate it periodically according to security best practices.

