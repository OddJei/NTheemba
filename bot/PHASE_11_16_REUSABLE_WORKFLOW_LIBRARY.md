# Phase 11.16 — Reusable Capability Workflow Library

Ntheemba workflows are activated by capabilities, not business names.

Current reusable workflow families:

- public business information and FAQs;
- client identification and minimal client creation;
- product catalogue and product ordering;
- service catalogue and appointment creation;
- loyalty status explanation;
- human handover.

Serah's Glow is the first business enabling the client, service, appointment, and loyalty capabilities, but none of these workflow meanings are named after Serah.

Compound requests are represented by `ConversationPlan` and ordered `PlannedWorkflow` children. For example, a service-plus-hair request can require both appointment and product-order capabilities while still producing separate operational records.

Main implementation:

- `ntheemba/domain/conversation_plan.py`
- `ntheemba/application/conversation_planner.py`
- `ntheemba/workflows/loyalty.py`
- existing catalogue, order, booking, information, and handover workflows.
