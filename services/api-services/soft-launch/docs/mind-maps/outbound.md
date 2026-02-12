**Outbound — Focused Mind Map**

- **Responsibility**: Consume cleaned outbound intents, persist outbound messages (via ICE), deliver messages to platform‑specific delivery workers, and record delivery receipts.

- **Inputs**:
  - `outbound:request` messages produced by Custom Bot or other services. Payload should include `to`, `from`, `reply_text`, `meta.platform`, and `bot_id` only.

- **Core behavior**:
  - Strip enrichment safely; do not include business blobs, product snapshots, or secrets in delivery payloads.
  - Persist the outbound message by calling ICE `POST /api/v1/messages/log` (ICE writes authoritative records/Outbox entries).
  - Publish the cleaned payload to platform queue `outbound:{platform}` for platform workers to deliver (WhatsApp, SMS, Push).

- **Delivery & receipts**:
  - Platform workers call provider adapters and return delivery receipts (message id, status). Persist receipts via ICE (or an Outbox write) and emit `outbound.delivered` / `outbound.failed` events to Outbox.
  - Delivery receipt events are authoritative and used for analytics and billing where applicable.

- **Retries & DLQ**:
  - Use exponential backoff for transient provider errors; after N attempts, move to `outbound:deadletter` with full context.

- **Observability & audit**:
  - Metrics: `outbound.sent_total`, `outbound.failed_total`, `outbound.latency`.
  - Persist audit records for each send attempt; ensure `X-Correlation-Id` is included on persistence and events.

- **Security**:
  - Ensure no sensitive tokens are sent to external providers; provider credentials live in outbound service config only.

-- End
**Outbound Service — Focused Mind Map**

- **Responsibility**: Consume enriched outbound requests, strip enrichment, persist outbound message via ICE, publish to platform‑specific outbound queues/workers.

- **Key topics / topics**:
  - Consume: `outbound:request`
  - Publish: `outbound:{platform}`
  - ICE persistence: call ICE `POST /v1/outbound` (persist then publish)

- **Strip rules**:
  - Keep only: `to`, `from`, `reply_text`, `meta.platform`, `bot_id`, optional `media` refs (signed URLs).
  - Remove all internal blobs (business_blob, cart_blob, product_snapshots).

- **Persistence**:
  - Outbound service must call ICE to persist outbound message before publishing to `outbound:{platform}`.
  - ICE will append to cycle snapshot and OOB and emit audit event.

- **Failure handling**:
  - If ICE persist fails, retry with backoff; if persistent failure, write to `outbound:deadletter`.

- **Example outbound payload (stripped)**

```json
{
  "to":"260955000111",
  "from":"260977000222",
  "reply_text":"Your order #ORD-123 is confirmed",
  "meta":{ "platform":"whatsapp" },
  "bot_id":"bot-123"
}
```

- **Mermaid flow**:

```mermaid
flowchart TD
  A[Custom Bot] --> B[outbound:request]
  B --> C[Outbound Service Strip Payload]
  C --> D[Call ICE Persist]
  D --> E[Publish -> outbound:{platform}]
  D --> F[Audit & OOB Update]
```