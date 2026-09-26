# Phase 11.20 Release Notes

## Release scope

This release completes the Ntheemba-side capability-neutral foundation from Phase 11.12 through the Phase 11.20 contract freeze.

## Most important rule

Ntheemba owns the capability and TradeFlow-method catalogues. A connected business can only declare support for known entries.

Unknown entries are:

- rejected;
- recorded once for review;
- excluded from runtime permissions;
- never auto-executed;
- never treated as a new capability.

## Live developer scenarios

The multi-conversation workspace currently executes:

- standard product discovery and complete orders;
- delivery/collection capability enforcement;
- Serah client recognition and minimal client creation;
- Serah service discovery and appointment creation;
- Serah product orders;
- Serah loyalty-status explanation using TradeFlow-calculated results;
- handover;
- duplicate handling and trace inspection;
- same customer across isolated business sessions.

## Contract-ready but not connected to production yet

- live Apps Script adapters for the standard and Serah applications;
- production OpenWA/Redis Streams worker;
- appointment reschedule and cancellation conversations;
- durable Redis/PostgreSQL state;
- compound service-plus-product plan persistence.

The canonical operation and capability contracts for later appointment changes exist, but the current simulator's complete live booking example covers appointment creation. Production app modifications and durable storage remain separate follow-on work.

## Production safety

No uploaded TradeFlow Apps Script application and no legacy WhatsApp Node project was modified or deployed by this release. The package contains the Ntheemba contracts, reference adapters, in-memory implementations, simulator, tests, and documentation needed before those integrations are connected.
