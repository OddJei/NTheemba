MSME Engine Refactor Checklist
===============================

Overview
--------

This checklist captures the concrete refactor tasks required to implement the canonical S2S policies defined in the mind-maps (Outbox-first, HMAC-only provider callbacks, idempotency-reject semantics for financial writes, forward MSME JWTs for attribution, 24h business cache, dispatcher secret, etc.).

Notes
-----

- I inspected the available mind-maps and the current `msme-engine` codebase. Some changes (e.g., `PaymentInitiation` persistence) are already in place and must be validated.
- Do not implement ambiguous items until the clarifying questions below are answered.

Checklist (high-level tasks)
----------------------------

- [ ] 1) Validate existing `PaymentInitiation` implementation
  - Confirm schema fields, indexes, and how depositId/reference_id are stored.
  - Ensure tests cover subscribe_and_pay persistence path.

- [ ] 2) Implement Outbox-first for payment events
  - On authoritative event (payment_success), correlate to `PaymentInitiation`.
  - Only create `OutboxEvent` when `PaymentInitiation.affiliate_id` is present.
  - Ensure Outbox row is written in the same DB transaction that updates `PaymentInitiation` status if possible.

- [ ] 3) Harden idempotency for financial endpoints
  - Enforce idempotency keys for `subscribe_and_pay` and payment callbacks.
  - Policy: reject duplicate conflicting writes with HTTP 409 for financial-affecting requests (confirm exact behavior below).
  - Add DB constraints or idempotency-record logic to prevent double-commits.

- [ ] 4) Enforce HMAC-only callbacks from Payment-Revenue
  - Add signature verification middleware for `/events/payment_success` and `/events/payment_failed`.
  - Define secret rotation/storage (where to store HMAC secret).
  - Update Payment-Revenue to sign callbacks (coordination task).

- [ ] 5) Outbox Dispatcher updates
  - Ensure dispatcher reads `OutboxEvent` rows and posts to target services with a dedicated internal secret header.
  - Add config for dispatcher secret & rotate support.
  - Ensure dispatcher marks events attempted/completed and supports retry/backoff.

- [ ] 6) Tests and E2E
  - Integration test: `subscribe_and_pay` -> Payment-Revenue initiate -> payment callback -> MSME marks subscription active and emits Outbox only when affiliate present.
  - Add idempotency tests: replay callback should be idempotent (duplicate callback yields safe outcome / 409 where applicable).

- [ ] 7) Cross-service changes to coordinate
  - Payment-Revenue: support signed callbacks and documented HMAC header.
  - Affiliate-Engine: accept `msme.subscription.payment_succeeded` events from Outbox dispatcher authenticated with internal secret.
  - Order-Delivery: remove synchronous affiliate dispatch; move to Outbox consumer.
  - ICE: switch authoritative publishes to Outbox and forward MSME JWT when calling downstream.

- [ ] 8) Link affiliate-role users to Affiliate-Engine affiliates
  - Ensure users with the `affiliate` role in MSME are linked to the canonical affiliate records in `affiliate-engine`.
  - Decide storage: add `affiliate_id` FK column on `users` or maintain a `msme_affiliate_links` mapping table.
  - Add APIs or migrations to backfill existing affiliate users.
  - Add tests to validate link integrity and that affiliate-originated flows include `affiliate_id` in `PaymentInitiation`.

- [ ] 8) Caching & single-flight policies
  - Align `business` details cache TTLs to 24h across services.
  - Ensure Redis-based single-flight locks remain on hydrate/reserve/confirm hot paths.

- [ ] 9) Observability & audit
  - Propagate `X-Correlation-Id` to outbox payloads and dispatched requests.
  - Emit audit events for critical state transitions (initiation created, outbox written, initiation completed).

- [ ] 10) Docs & rollout
  - Update `docs/mind-maps/*` with final contract (claims names, HMAC header name, dispatcher secret name).
  - Add `refactor.md` (this file) and a short rollout plan with a canary strategy and monitoring checks.

Implementation details & code pointers
-------------------------------------

- Files to change in `msme-engine` (recommended):
  - `src/app/models.py`: confirm `PaymentInitiation` and `OutboxEvent` fields and indexes.
  - `src/app/main.py`: `POST /business/{id}/subscribe_and_pay` (initiation persist), `POST /events/payment_success` (correlate initiation + write outbox), signature verification middleware.
  - `src/app/outbox_dispatcher.py` or equivalent: ensure it reads `OutboxEvent` rows, signs requests with internal secret, and marks attempts.
  - `tests/`: add integration tests to `tests/test_business.py` and idempotency tests.

Risk & Rollback
----------------

- Writing Outbox records must be transactional with state changes to avoid duplication or lost events. If DB transactions across services are not possible, add compensating checks or delivery guarantees in dispatcher.
- Changing callbacks to HMAC-only requires coordination with Payment-Revenue; if rollout fails, revert to a temporary fallback that verifies both HMAC and previous auth.

Clarifying questions (REQUIRED — do NOT implement until answered)
-----------------------------------------------------------------

1) HMAC secret location and naming: where should the Payment-Revenue HMAC secret be stored for MSME verification? (options: environment variable `PAYMENT_REVENUE_HMAC_SECRET`, Vault path, or existing config service)
answer: environment variable `PAYMENT_REVENUE_HMAC_SECRET`
2) Idempotency policy for payment callbacks: should duplicate callbacks be treated as idempotent (return 200 and ignore repeat) or as conflicts (return 409) for financial-affecting duplications? Specify by endpoint.
answer: For payment callbacks, duplicate callbacks with the same `event_id` should be treated as idempotent and return 200 while ignoring the repeat. However, if a callback attempts to update a `PaymentInitiation` that has already been marked as completed (e.g., status is already 'succeeded' or 'failed'), it should return a 409 Conflict to indicate a conflicting write attempt. This allows for safe retries while preventing unintended state changes from duplicate callbacks.
3) Correlation key for initiation lookup: should `payment_success` correlate to `PaymentInitiation` by `depositId` (preferred) or by `business_id + latest pending` (current best-effort approach)? If depositId exists, what claim/field name is used in the callback payload? (e.g., `deposit_id` or `reference_id`)
answer: The `payment_success` callback should correlate to `PaymentInitiation` by `depositId`, which is the preferred approach for accuracy. The callback payload from Payment-Revenue will include this identifier in a field named `reference_id`. MSME should use the `reference_id` from the callback to look up the corresponding `PaymentInitiation` record and update its status accordingly. This ensures a reliable correlation between the payment event and the initiation record, even if multiple initiations exist for the same business.
4) Affiliate claim name in forwarded JWT: which claim contains the affiliate id in the MSME-issued JWT? (e.g., `affiliate_id`, `affiliate`, or nested in `claims.aff`)
answer: The affiliate id in the MSME-issued JWT is contained in the claim named `affiliate_id`. When MSME forwards the JWT to downstream services for attribution-sensitive calls, it should ensure that the `affiliate_id` claim is included and correctly propagated. This allows downstream services like ICE, Order-Delivery, and Affiliate-Engine to perform accurate attribution based on the affiliate context provided in the token.
5) Outbox event targets and auth header name: confirm the Outbox dispatcher should set header `X-Internal-Secret` (or another name) when posting to `affiliate-engine`.
answer: Yes, the Outbox dispatcher should set the header `X-Internal-Secret` when posting events to `affiliate-engine` and any other internal services that require authentication. This header will contain a shared secret that is configured in both MSME and the target service to verify that incoming requests are legitimately from the Outbox dispatcher. The exact value of the secret should be stored securely (e.g., in environment variables or a secrets manager) and rotated periodically according to security best practices.
6) Transactional requirement for Outbox write: must the Outbox insert and `PaymentInitiation` status update be strictly in the same DB transaction, or is best-effort with compensating logic acceptable?
answer: Ideally, the Outbox insert and `PaymentInitiation` status update should be in the same DB transaction to ensure atomicity and prevent scenarios where the initiation is marked as completed but the Outbox event is not created (or vice versa). However, if the current architecture does not support this level of transactional integrity across these operations, a best-effort approach with compensating logic can be implemented. In this case, the system should include checks in the Outbox dispatcher to detect and handle any discrepancies (e.g., if a `PaymentInitiation` is marked as succeeded but no corresponding Outbox event exists, the dispatcher could create a compensating event or alert for manual review). This is not ideal but can be an acceptable interim solution while working towards a more robust transactional design.
7) Test environments and fixtures: do you have an integration test harness or mocked Payment-Revenue service to run end-to-end tests, or should I add a local mock in tests for CI?
answer: we will have to use the real payment-revenue the services uses a sandbox environment for testing. We can create test fixtures in the payment-revenue sandbox to simulate the expected callbacks for our integration tests. This allows us to run end-to-end tests in CI without needing to maintain a separate local mock service, while still ensuring that we are testing against the actual behavior of the payment-revenue service.

Next steps after answers
------------------------

- With your answers I will produce a prioritized, step-by-step patch plan and implement the smallest safe change first (likely signature verification + Outbox write transactional fix and tests).

---
Generated: %s
