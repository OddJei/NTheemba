# Phase 11.19 — Legacy OpenWA Gateway Contract

The legacy OpenWA transport is wrapped behind provider-neutral envelopes instead of being allowed to shape Ntheemba core.

The legacy adapter maps a registered OpenWA session to an exact Ntheemba channel. A payload-supplied business ID is not trusted.

The in-memory reliable queue models the acknowledgement semantics required for the Phase 12 Redis Streams adapter:

```text
enqueue → claim → process → acknowledge
                    ├── retry
                    └── dead letter
```

This prevents the destructive-pop failure mode of `BLPOP`, where a process crash can lose a claimed message.

This phase does not rewrite or deploy the legacy Node/OpenWA project. It defines and tests the contract Ntheemba expects from it.

Main implementation:

- `ntheemba/adapters/gateway/legacy_openwa.py`
- `ntheemba/adapters/gateway/in_memory.py`
- `ntheemba/ports/gateway.py`
