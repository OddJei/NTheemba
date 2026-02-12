Payment-Revenue Refactor Checklist
=================================

Purpose
-------
Implement HMAC-signed callbacks, idempotent deposit initiation, and an Outbox-aware pattern so Payment-Revenue can be safely used as an authoritative payment provider for MSME and Affiliate flows.

Checklist
---------
- [ ] 1) Add HMAC signing for all outgoing callbacks to MSME
  - Define header name (e.g., `X-Payment-Signature`) and hashing algorithm (HMAC-SHA256).
  - Provide configurable secret storage (env var or Vault).
  - Add tests to verify signatures are valid and reject unsigned requests.

- [ ] 2) Make deposit initiation idempotent
  - Ensure repeated `POST /deposits/initiate` with same `depositId` is safe (idempotent)
  - Return consistent result for retries.

- [ ] 3) Include deposit reference (depositId) in callbacks
  - Ensure callbacks include a stable `deposit_id` and original `reference_id` so MSME can correlate.

- [ ] 4) Provide sandbox/mock endpoints for integration tests
  - Allow MSME tests to run locally against a mock Payment-Revenue that signs callbacks.

- [ ] 5) Coordinate rollout with MSME
  - Agree secret storage, header names, and timing for switching MSME to HMAC-only verification.

Clarifying questions
--------------------
1) Which secret storage do you want to use for HMAC secrets? (env var like `PAYMENT_REVENUE_HMAC_SECRET` or Vault)
answer: We will use an environment variable named `PAYMENT_REVENUE_HMAC_SECRET` for storing the HMAC secret used for signing callbacks. This allows for easy configuration and rotation of the secret without needing to integrate with a more complex secrets management system like Vault, which may be overkill for this use case. The environment variable can be set in the deployment configuration for Payment-Revenue and should be kept secure to prevent unauthorized access to the signing key.
2) Confirm callback field names: `deposit_id` and `reference_id`? (or `depositId`/`referenceId`?)
answer: We will use `deposit_id` and `reference_id` as the field names in the callbacks for consistency with common naming conventions in JSON APIs. This means that when Payment-Revenue sends callbacks to MSME, it will include these fields in the payload to allow MSME to correlate the callback with the original deposit initiation request. Using snake_case for these field names is a common practice in Python-based services and should be clear and consistent for developers working with the API.
3) Should Payment-Revenue also accept forwarded Authorization from MSME for audit/tracing? (recommended)
answer: Yes, Payment-Revenue should accept the forwarded `Authorization` header from MSME when initiating payments. This allows Payment-Revenue to have the necessary context for audit and tracing purposes, as it can log the user and business information contained in the token. When MSME initiates a payment by calling `POST /pawapay/deposits/initiate`, it should include the caller's `Authorization` header, which contains the JWT with claims such as `sub`, `role`, `business_id`, and `affiliate_id`. Payment-Revenue can then log this information along with the payment initiation details, providing a complete audit trail and enabling better observability across services.

