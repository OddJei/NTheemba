# Frontend Handoff — Legal Team

This document summarizes the frontend implementation with focus on compliance, privacy, data retention, and contract points related to payments and subscriptions.

## Overview

- Project: `dashboards` (React + TypeScript + Vite + Tailwind)
- Key legal touchpoints: payments, data retention, PII handling, provider terms, audit logs, and export of transaction records.

## Where payment flows live

- The frontend triggers payment creation and displays status using `src/components/shared/BillingPayment.tsx`.
- The demo flows live in `src/pages/SubscriptionDemo.tsx` and call the UI components used in production.

## PII and data handling

- The frontend collects minimal PII required for payments: phone number and payment provider. Do not collect or persist card data in the frontend.
- Store/transfer phone numbers in E.164 format where possible.
- All sensitive exchanges (payment initiation, tokenized provider references) should be proxied through the backend over HTTPS.

## Required backend guarantees (contractual)

1. All provider credentials (API keys, secrets) are stored securely on the backend and never embedded in the frontend bundle.
2. Payment requests from the frontend must be authenticated and authorized before initiating provider calls.
3. The backend must return a transaction id and provider reference and store a full audit trail for each transaction.
4. Webhooks from providers should be validated (signature verification) and only accepted by the backend endpoint.

## Retention and audit

- Transaction records should be immutable and include request payload, response payload, providerRef, and timestamps.
- Retain logs and transaction records according to local regulations; consult the Financial team for the retention policy (e.g., 7 years).

## Compliance check list

- Data encryption in transit (TLS) — required for all endpoints used by frontend
- No secrets in frontend bundles
- PII minimization (only phone number for mobile money)
- Webhook signature verification and replay protection
- Ability to export daily reconciliation CSV and searchable audit logs

## Consent and UI wording recommendations

- The Billing UI (`BillingPayment.tsx`) must present the following to the user before initiating payment:
  - The amount to be charged and currency
  - The payment provider name
  - The payer phone number (confirm before submitting)
  - A link to Terms & Privacy (backend-powered canonical URLs)

## Dispute and refund flow (recommended)

1. Provide backend endpoints to create and query refund requests tied to original transaction ids.
2. Ensure UI surfaces refund status (requested, processing, completed, rejected) in `SubscriptionManagement`.
3. Preserve providerRef and backend transaction ids for legal evidence.

## Third-party provider terms

- Each provider (MTN, Airtel, Zamtel or others) will have its own SLA, chargeback rules, and fees. Legal should obtain provider contracts and confirm whether the provider allows refunds initiated by the platform.

## Incident response

- Define who is notified on failed webhooks, mass payment failures, or suspicious activity. Keep a runbook with roles and contact points.

## Next steps for Legal Team

1. Confirm retention period with Financial team and update privacy policy & terms if necessary.
2. Review provider contracts for refund windows and obligations.
3. Approve required user-facing wording for the Billing UI.
4. Define the record-keeping and audit requirements for regulatory compliance.

---
If you'd like, I can also extract the exact UI copy and create a small set of screenshots or a UI text spec to include in the Terms & Privacy review.
