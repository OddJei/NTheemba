# Phase 12.3 — Durable Customer Identity and Consent

Customer phone numbers are normalized to E.164 and mapped to one platform customer. Every business receives a separate `business_customers` relationship.

Platform identity may contain a consented display name and preferred language. Business relationships may contain private preferred names, activity counts, loyalty state and metadata.

Consent decisions are stored independently for:

- cross-business recognition;
- saved platform checkout details;
- conversation retention;
- marketing messages.

Revoking a consent changes what future conversations may reuse; it does not expose another business's private records.
