# Ntheemba Operator UI/UX Playbook

## Purpose and navigation

The operator workspace is for an NDS operator managing a business without needing Ntheemba implementation knowledge. It provides Overview, Businesses, Business Detail, Business Services and System Status. Developer tools remain separate under `/dev/*`, are available only in development/test when enabled, and retain their precise technical language.

## Plain language and help

Use Active, Paused, Connected, Not connected, Needs attention, Not configured and Working normally. The canonical capability IDs remain server-side authority. The operator labels are: Business information, Opening hours, Frequently asked questions, Find existing customers, Create customer profiles, Product search, Orders, Delivery, Collection, Services, Book appointments, Reschedule appointments, Cancel appointments, Loyalty information, and Speak to staff / Human support.

`?` explains a field or service briefly. `!` is reserved for consequential actions such as pausing a business. Every page has Help describing the page and its principal action. Technical details are collapsed by default and may include identifiers and configuration type but never a token, credential reference, secret, endpoint, or integration configuration.

## Channels, connections, and safety

Use Primary WhatsApp and Secondary WhatsApp rather than role enums. Integration and catalogue screens disclose only connection state. The workspace uses an HttpOnly, SameSite server-side operator session and CSRF-protected mutation forms; it never stores privileged tokens in browser storage or returns raw credentials. Business and capability changes call the existing audited operator control-plane service; no UI database or duplicate business registry exists.

## Accessibility and responsive behavior

Inputs have labels, focus-visible styles are high-contrast, status is written as text as well as styled, all details use native keyboard-accessible disclosure, and controls retain 44px touch targets at 390px. The header, cards, forms and service rows wrap instead of clipping.

## Decisions and Definition of Done

The UI is server-rendered FastAPI to avoid a new frontend framework. It does not change conversation routing, Redis, PostgreSQL ownership, capabilities, gateway behavior, or developer tools. Done means ordinary-language business management works through the existing control plane; developer tools remain separate; technical detail is progressive; secrets are absent; and focused plus full-suite validation are recorded.
