Outbox-Dispatcher Refactor Checklist
===================================

Purpose
-------
Harden the dispatcher that reads Outbox rows and delivers them to target services using a dedicated internal secret, robust retries, backoff, and observability.

Checklist
---------
- [ ] 1) Add configuration for dedicated internal secret
  - Env var name suggestion: `OUTBOX_INTERNAL_SECRET`
  - Ensure secret rotation path is documented.

- [ ] 2) Attach internal secret header to dispatched requests
  - Header name suggestion: `X-Internal-Secret`.

- [ ] 3) Improve retry/backoff and dead-letter handling
  - Use exponential backoff, mark events failed after N attempts and provide DLQ.

- [ ] 4) Add observability and metrics
  - Emit counters for attempts, successes, failures; logs include `correlation_id` and `event_id`.

- [ ] 5) Ensure idempotent posting and dedupe headers
  - Include `X-Idempotency-Key` when dispatcher calls targets where appropriate.

Clarifying questions
--------------------
1) Confirm header name for internal secret (`X-Internal-Secret` OK?), and which services will accept it (affiliate-engine, order-delivery, etc.).
anser: Yes, `X-Internal-Secret` is a suitable header name for the internal secret used by the Outbox dispatcher when posting events to target services. The services that will accept this header for authentication include `affiliate-engine`, `order-delivery`, and any other internal services that are configured to recognize this secret for verifying incoming requests from the dispatcher. Each target service should have logic to validate the presence and correctness of the `X-Internal-Secret` header to ensure that only authorized requests are processed.
2) How many retry attempts before DLQ (suggest 5)?
answer: A common practice for retrying failed events is to allow for 5 attempts before marking the event as failed and moving it to a dead-letter queue (DLQ). This allows for transient issues to be resolved while preventing infinite retry loops. However, the exact number of retries can be adjusted based on the expected failure modes and the criticality of the events being dispatched. It's important to monitor the retry behavior and adjust the threshold as needed based on operational experience.
3)Quick clarifying question before I implement the central dispatcher: should the dispatcher poll each service's Outbox table directly (needs DB credentials per service), or should each service expose a small /outbox/pending HTTP endpoint the dispatcher will call to fetch and ack events? Choose one.

answer: The recommended approach is for each service to expose a small `/outbox/pending` HTTP endpoint that the dispatcher will call to fetch and acknowledge events. This approach abstracts away the database access from the dispatcher, allowing each service to manage its own Outbox table and credentials securely. The dispatcher can periodically poll these endpoints to retrieve pending events, process them, and then acknowledge successful processing back to the service. This design promotes better separation of concerns, enhances security by avoiding direct database access, and allows for more flexible scaling of the dispatcher and target services independently.

1) Response shape — should each `/outbox/pending` return JSON array of events with fields: `id`, `event_type`, `payload`, `dedupe_key`, `destination`, `attempts`, `scheduled_at`, `correlation_id`? (yes/no or edits)
answer: Yes, the `/outbox/pending` endpoint should return a JSON array of events with the specified fields: `id`, `event_type`, `payload`, `dedupe_key`, `destination`, `attempts`, `scheduled_at`, and `correlation_id`. This structure provides all the necessary information for the dispatcher to process each event correctly, handle idempotency with the `dedupe_key`, manage retries with the `attempts` count, and maintain observability with the `correlation_id`. Additionally, including the `destination` field allows the dispatcher to route events to the appropriate target services based on their configuration.

2) Ack contract — dispatcher will POST `{"ids": ["id1","id2",...]}` to `/outbox/ack` on the same service to mark success; is POST `/outbox/ack` acceptable? (yes/no or alternative)
answer: Yes, using a POST request to `/outbox/ack` with a payload of `{"ids": ["id1","id2",...]}` is an acceptable approach for acknowledging successful processing of events. This allows the dispatcher to inform the service which specific events have been processed successfully, enabling the service to remove them from the pending queue or mark them as completed. The POST method is appropriate here as it indicates that the request is performing an action (acknowledging events) rather than retrieving data, which aligns well with RESTful API design principles.

3) Polling/batch defaults — use `batch_size=50` and `poll_interval=5s` (configurable); OK?
answer: Yes, using a default `batch_size` of 50 and a `poll_interval` of 5 seconds is a reasonable starting point for the Outbox dispatcher. This allows the dispatcher to process events in manageable batches while maintaining a responsive polling frequency. However, these values should be configurable to allow for adjustments based on the volume of events, processing time, and operational requirements. It's important to monitor the performance of the dispatcher and adjust these parameters as needed to optimize throughput and minimize latency without overwhelming the target services.

4) Auth — dispatcher will call `/outbox/pending` and `/outbox/ack` with `X-Internal-Secret`; services validate that header. Confirm?
answer: Yes, the dispatcher should include the `X-Internal-Secret` header when calling both the `/outbox/pending` and `/outbox/ack` endpoints. Each target service should validate the presence and correctness of this header to ensure that only authorized requests from the dispatcher are processed. This approach provides a secure mechanism for authenticating the dispatcher and helps prevent unauthorized access to the Outbox endpoints. Make sure to implement proper error handling in the dispatcher for cases where the secret is invalid or missing, so that it can log these incidents and take appropriate action.

5) Failures — if a service returns non-200, dispatcher will backoff and retry later (DLQ after 5 attempts). Accept?
answer: Yes, if a service returns a non-200 status code in response to the dispatcher's request, the dispatcher should implement an exponential backoff strategy and retry the request after a delay. If the dispatcher encounters 5 consecutive failures for the same event, it should mark the event as failed and move it to a dead-letter queue (DLQ) for further investigation. This approach allows for transient issues to be resolved while preventing infinite retry loops and ensuring that problematic events are flagged for manual review.
