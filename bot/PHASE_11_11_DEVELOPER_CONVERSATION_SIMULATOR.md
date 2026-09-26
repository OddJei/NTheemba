# Phase 11.11 — Developer Conversation Simulator

Phase 11.11 adds a protected, developer-only chat simulator that sends realistic
messages through the same Ntheemba application service, interpreter, workflow
router, session coordinator, workflows, dependency ports, publisher, and tracer
used by the runtime.

The simulator replaces only the external WhatsApp gateway. It does not introduce
a second or simplified conversation engine.

## Run locally

From the project root in Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
$env:NTHEEMBA_ENVIRONMENT = "development"
$env:NTHEEMBA_DEV_TOOLS_ENABLED = "true"
python -m uvicorn ntheemba.main:app --reload
```

Open:

- Conversation simulator: `http://127.0.0.1:8000/dev/simulator`
- Trace and dependency console: `http://127.0.0.1:8000/dev/console`

The existing developer network and token policy also protects the simulator.
When `NTHEEMBA_DEV_TOOLS_TOKEN` is configured, enter the token in the simulator
before calling its APIs.

## Runtime path

```text
Browser chat simulator
  -> POST /dev/simulator/messages
  -> ProcessMessageCommand
  -> NtheembaService
  -> message deduplication
  -> session open
  -> interpretation
  -> workflow routing
  -> transition validation
  -> real workflow handler
  -> NCPC / TradeFlow simulator ports
  -> session commit
  -> outgoing publisher simulator
  -> reply returned to the browser
```

The simulator uses the real catalogue, order, booking, information, and handover
workflows. In-memory seeded ports supply deterministic business data while still
respecting the Phase 11.6 fake-dependency controls.

## User interface

The protected page at `/dev/simulator` provides:

- a WhatsApp-style conversation pane;
- seeded business selection;
- configurable customer identity;
- quick-message scenarios;
- live pipeline polling while a message is processing;
- stage status and duration inspection;
- safe event attributes and failure details;
- current session-state inspection;
- replay with the same or a fresh message ID;
- conversation expiration and reset controls;
- links to the full observability and dependency console.

The pipeline panel follows these instrumented nodes:

```text
message.process
message.deduplicate
session.open
message.interpret
workflow.route
transition.validate
workflow.execute
session.commit
reply.publish
message.release_claim
```

Injected dependency latency is visible while a message remains in flight. A
failed stage is displayed using the actual trace emitted by the pipeline.

## Seeded scenarios

### Harvest Big Shop

The seeded grocery scenario supports public information, FAQ questions, product
catalogue searches, and a complete order-request flow.

Example order conversation:

```text
Show me cooking oil
1
Order this
2
delivery
Mufulira Central near the post office
James +260970000001
confirm
```

### Serah's Glow Lounge

The seeded salon scenario supports service discovery and a complete appointment
booking flow.

Example booking conversation:

```text
I want to book an appointment
1
<the YYYY-MM-DD date shown in the quick messages>
1
anyone
James +260970000001
confirm
```

## Developer API

```text
GET    /dev/simulator
GET    /dev/simulator/businesses
POST   /dev/simulator/messages
GET    /dev/simulator/requests/{request_id}/trace
GET    /dev/simulator/conversations/{business_id}/{customer_id}
DELETE /dev/simulator/conversations/{business_id}/{customer_id}
POST   /dev/simulator/conversations/{business_id}/{customer_id}/expire
POST   /dev/simulator/conversations/{business_id}/{customer_id}/replay
```

Example message request:

```json
{
  "business_id": "harvest-big-shop",
  "customer_id": "260970000001",
  "message_id": "sim-message-001",
  "request_id": "sim-request-001",
  "text": "Show me cooking oil"
}
```

The response includes the processing outcome, captured customer-visible replies,
the trace ID, and the current safe session snapshot.

## Deduplication and replay

Replay with `same_message_id=true` deliberately reuses the previous inbound
message ID. This exercises the real deduplication branch and should produce a
`duplicate` outcome without reopening the session.

Replay with `same_message_id=false` creates a new message and request ID while
preserving the conversation text and state.

Reset removes the in-memory session and releases message IDs created by that
simulated conversation so the same scenario can be run again.

## Fault injection

The simulator shares the Phase 11.6 `FakeDependencyController`. Configure a
failure or latency under `/dev/console`, then send the next chat message.
Supported controlled boundaries include:

- interpreter;
- session repository;
- session lock;
- deduplication;
- NCPC;
- TradeFlow;
- publisher;
- audit.

For example, fail the publisher operation `publish_many`, then send a message.
The conversation result reports an infrastructure failure and the live pipeline
marks `reply.publish` as failed.

## Security and lifecycle

- Registered only when developer tooling is active.
- Not instantiated in staging or production.
- Protected by loopback/network restrictions and optional Bearer authentication.
- Cross-origin requests are rejected.
- UI and API responses use no-store and defensive browser headers.
- The UI is self-contained and loads no third-party scripts or assets.
- Trace values pass through the existing redaction and bounding layer.
- Simulator state is in memory and disappears when the process restarts.

## Validation

Phase 11.11 adds HTTP and integration tests for:

- simulator page security headers;
- seeded business discovery;
- real pipeline execution and traces;
- complete order-state continuity;
- duplicate replay behavior;
- reset and message-ID release;
- fake publisher failure propagation;
- production route isolation.

The complete automated suite contains 292 passing tests.
