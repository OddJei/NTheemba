**OOB (Out Of Band) Store — Focused Mind Map**

- **Responsibility**: Short‑lived Redis store for session-scoped snapshots (hydration blobs, cart snapshot, last_node_executed, diagnostics). Acts as cache between turns for fast reads.

- **Key details**:
  - Key pattern: `oob:{session_id}` (Redis hash)
  - TTL: 24 hours
  - Update strategy: optimistic CAS using `version`/`etag` field; up to 3 retries with exponential backoff.

- **Stored objects**:
  - `hydration_blob`, `cart_snapshot`, `order_snapshot`, `last_node_executed`, `diagnostics`

- **Example**

```json
{
  "session_id":"sess-456",
  "version":12,
  "hydration_blob":{...},
  "cart_snapshot":{...},
  "last_node_executed":"node-ask-qty"
}
```

- **Mermaid flow**:

```mermaid
flowchart TD
  A[ICE hydrate] --> B[Write oob:{session_id} with CAS]
  C[Bot Service] --> D[Read oob:{session_id}]
  D --> E[If missing -> call ICE authoritative]
```

- **Operational notes**:
  - Monitor CAS conflict rates; tune retry/backoff.
  - Use OOB for quick turn latency; persist canonical state in Postgres via ICE for durability.
