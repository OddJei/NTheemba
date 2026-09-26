# Ntheemba Phase 12 Release Notes

## Release basis

This release starts from Phase 11.20 and preserves its capability, channel,
customer, TradeFlow, gateway, and simulator contracts.

## Added

- Redis runtime, namespaced keys, versioned session serialization, archives,
  locks, deduplication, and idempotency.
- Redis Streams gateway queue with claim, acknowledgement, retry, stale pending
  recovery, and inbound/outbound dead-letter streams.
- Inbound and outbound worker iterations with maximum-attempt handling.
- Authenticated `/api/v1/gateway/inbound` ingestion.
- PostgreSQL business/channel registry, declarations, unsupported observations,
  platform customers, private client links, consents, addresses, preferences,
  messages, summaries, and questions.
- Forced row-level security for tenant/customer-scoped records.
- Consent-enforced cross-business names and saved checkout details.
- Storage lifecycle, readiness, developer diagnostics, retention cleanup,
  Docker Compose, migrations, and Windows Psycopg event-loop handling.
- Durable TradeFlow write idempotency and durable outgoing reply publication.

## Capability authority

Database declarations do not extend Ntheemba. Unknown capability names and
TradeFlow operations are rejected and recorded. Activation still requires an
explicit Ntheemba enum entry, capability definition, operation contract,
workflow implementation, tests, and approval.

## Not included

- No production Standard TradeFlow Apps Script was modified.
- No production Serah's Glow Apps Script was modified.
- No legacy OpenWA Node deployment was modified.
- Real channel IDs, credentials, and provider sending adapters remain deployment
  configuration work.
