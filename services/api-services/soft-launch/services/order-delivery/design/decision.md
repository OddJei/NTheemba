# Architecture Decision (Soft Launch): Fused Order + Delivery

## Decision
For **soft-launch**, implement a single deployable service that owns both **Order** and **Delivery** (delivery-code handover).

## Why this fits soft-launch
- **Operational simplicity**: one service + one DB to run and debug.
- **Tight coupling**: delivery code generation/confirmation is a direct function of order state.
- **Cleaner state transitions**: avoid cross-service consistency problems while requirements are still evolving.

## How to keep it split-ready
- Keep internal modules separated (orders vs delivery).
- Publish outbox events (`delivery_code_generated`, `delivery_confirmed`, `order_paid`, `order_delivered`) so other services (audit/notification/messaging/payout) can integrate without tight coupling.

## When to split later
Split Delivery into its own service when:
- You add real courier/dispatch logistics
- Delivery becomes region/warehouse specific
- You need separate scaling/SLAs for delivery operations
