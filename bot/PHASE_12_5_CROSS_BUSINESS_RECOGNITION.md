# Phase 12.5 — Cross-Business Recognition and Faster Checkout

The normalized phone number lets Ntheemba identify a returning platform customer. Cross-business display-name reuse requires explicit `cross_business_recognition` consent.

Platform addresses/preferences require separate `saved_checkout_details` consent. A business may reuse details collected within its own customer relationship without exposing them to another business.

The order and booking workflows receive only a privacy-filtered context. When a permitted name, phone and delivery location are already available, checkout can advance directly to review.
