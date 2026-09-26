# Phase 11.15 — Platform Customer and Business Client Bridge

Ntheemba separates one minimal platform identity from private business-client relationships.

```text
PlatformCustomer
├── Harvest BusinessClientLink
├── AMAC BusinessClientLink
└── Serah's Glow BusinessClientLink
```

The platform identity contains only minimal reusable data such as normalized phone, confirmed preferred name, language, and consent status.

A business link contains the business ID and that business's external client ID. It does not expose another business's orders, appointments, loyalty, or notes.

For a business with `client.identify` and `client.create`, Ntheemba can:

- find a client by normalized phone;
- create a minimal client during checkout or booking;
- store the external client reference;
- reuse only permitted minimal details.

Serah's TradeFlow remains responsible for the actual client record and loyalty computation.

Main implementation:

- `ntheemba/domain/customers.py`
- `ntheemba/ports/customers.py`
- `ntheemba/adapters/customers/in_memory.py`
- `ntheemba/application/customer_bridge.py`
- `ntheemba/application/customer_workflow.py`
