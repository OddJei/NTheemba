# Phase 12.8 — Privacy, Tenant Isolation and Retention

Business-private PostgreSQL tables enable and force row-level security. Repository transactions set tenant/customer scope variables before queries.

The migration includes indexes for customer lookup, recent activity, unresolved questions and conversation history.

Retention cleanup is explicit and configurable. Customer deletion cascades from the platform customer to dependent consent, relationship, address, preference, message, summary and question records.
