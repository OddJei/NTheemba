# Phase 11.12 — Ntheemba-Owned Capability Catalogue

## Decision

Ntheemba is the sole authority for capability names, meanings, workflow mappings, and permitted TradeFlow operations.

A TradeFlow business may declare support only for identifiers that already exist in Ntheemba's canonical `CapabilityCatalogue`. It cannot create a capability by returning a new string.

## Runtime behavior

1. Load the business declaration.
2. Parse every declared identifier through the closed Ntheemba catalogue.
3. Enable known capabilities only.
4. Reject unknown identifiers.
5. Record each unknown identifier as an `UnsupportedDeclarationObservation`.
6. Never route a workflow from an unknown declaration.

Unknown declarations require a future explicit Ntheemba change containing:

- a canonical capability definition;
- workflow semantics;
- input and output contracts;
- TradeFlow operation mapping;
- validation and privacy rules;
- tests and approval.

## Main implementation

- `ntheemba/domain/capabilities.py`
- `ntheemba/application/capability_runtime.py`
- `ntheemba/ports/businesses.py`
- `ntheemba/adapters/businesses/in_memory.py`

## Trace nodes

- `capabilities.load`
- `capabilities.validate`

## Completion evidence

Known and unknown declarations are tested. Disabled capabilities are denied before workflow execution.
