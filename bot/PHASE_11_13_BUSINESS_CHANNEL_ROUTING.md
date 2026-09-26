# Phase 11.13 — Business Channel and Tenant Routing

Ntheemba resolves the business from the exact receiving channel before message interpretation.

```text
channel_instance_id → BusinessChannel → BusinessProfile → capabilities
```

Customer wording never selects the business. The same customer can therefore message Harvest and Serah's Glow at the same time without crossing sessions.

Session identity remains:

```text
business_id + platform_customer_id
```

The normalized provider-neutral envelope is implemented by `InboundGatewayMessage`. The business resolver validates:

- channel exists and is enabled;
- provider matches the registered channel;
- recipient number matches;
- business exists and is enabled;
- declared capabilities are canonical.

Unknown, disabled, or mismatched channels are rejected before interpretation.

Main implementation:

- `ntheemba/domain/gateway.py`
- `ntheemba/domain/business.py`
- `ntheemba/application/gateway_service.py`
- `ntheemba/application/capability_runtime.py`
