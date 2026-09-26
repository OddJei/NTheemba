"""Developer-only real gateway pipeline diagnostics."""

# ruff: noqa: E501

from __future__ import annotations

import json
from datetime import UTC, datetime
from secrets import token_urlsafe
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from ntheemba.domain.gateway import InboundGatewayMessage
from ntheemba.infrastructure.redis.keys import RedisKeyspace
from ntheemba.infrastructure.storage import StorageRuntime
from ntheemba.observability.sanitization import redact_mapping

router = APIRouter(prefix="/dev/pipeline", tags=["developer-pipeline"], include_in_schema=False)


class PipelineModeResponse(BaseModel):
    mode: str
    proof_scope: str
    dependencies: dict[str, str]
    warnings: tuple[str, ...]


class EnqueuePipelineMessageRequest(BaseModel):
    """Developer payload for enqueuing a real gateway-shaped inbound message."""

    model_config = ConfigDict(extra="forbid")

    channel_instance_id: Annotated[str, Field(min_length=1, max_length=200)]
    customer_phone: Annotated[str, Field(min_length=8, max_length=30)]
    text: Annotated[str, Field(min_length=1, max_length=4000)]
    # Keep the form default aligned with its synthetic N24 channel default.
    # The resolver validates the exact provider/session/recipient identity.
    recipient_phone: Annotated[str, Field(min_length=8, max_length=30)] = "+260970099024"
    provider: Annotated[str, Field(min_length=1, max_length=100)] = "developer"
    message_id: Annotated[str, Field(min_length=1, max_length=300)] = Field(
        default_factory=lambda: f"DEV-MSG-{uuid4()}"
    )
    request_id: Annotated[str, Field(min_length=1, max_length=200)] = Field(
        default_factory=lambda: f"DEV-REQ-{uuid4()}"
    )


class EnqueuePipelineMessageResponse(BaseModel):
    status: str
    delivery_id: str
    request_id: str
    mode: str
    warnings: tuple[str, ...]


class PipelineRequestStatusResponse(BaseModel):
    request_id: str
    storage: dict[str, object]
    inbound: tuple[dict[str, object], ...]
    outbound: tuple[dict[str, object], ...]
    inbound_dead_letters: tuple[dict[str, object], ...]
    outbound_dead_letters: tuple[dict[str, object], ...]
    audit_events: tuple[dict[str, object], ...]
    warnings: tuple[str, ...]


def _runtime(request: Request) -> StorageRuntime:
    runtime = getattr(request.app.state, "storage_runtime", None)
    if not isinstance(runtime, StorageRuntime):
        raise HTTPException(status_code=503, detail="Storage runtime is unavailable")
    return runtime


async def _mode(runtime: StorageRuntime) -> tuple[dict[str, str], tuple[str, ...]]:
    snapshot = await runtime.snapshot()
    dependencies = {
        "business_registry": snapshot.business_backend.upper(),
        "sessions": snapshot.session_backend.upper(),
        "queue": snapshot.gateway_queue_backend.upper(),
        "customers": snapshot.customer_backend.upper(),
        "redis": "READY" if snapshot.redis_ready else "UNAVAILABLE",
        "postgresql": "READY" if snapshot.postgres_ready else "UNAVAILABLE",
        "worker": "EXTERNAL_REQUIRED",
        "gateway_ingress": "SERVER_SIDE_DEV_ENQUEUE",
    }
    warnings: list[str] = []
    if snapshot.gateway_queue_backend != "redis":
        warnings.append("Gateway queue is not Redis; this cannot prove Redis Stream behavior.")
    if snapshot.session_backend != "redis":
        warnings.append("Sessions are not Redis; this cannot prove persisted Redis sessions.")
    if snapshot.business_backend != "postgres":
        warnings.append(
            "Business registry is not PostgreSQL; this cannot prove durable tenant routing."
        )
    if snapshot.customer_backend != "postgres":
        warnings.append(
            "Customer registry is not PostgreSQL; this cannot prove durable customer state."
        )
    if runtime.settings.gateway_shared_secret is None:
        warnings.append(
            "Gateway shared secret is not configured; external gateway auth is unproven."
        )
    warnings.append("A separate inbound worker must be running to process queued messages.")
    return dependencies, tuple(warnings)


@router.get("/mode", response_model=PipelineModeResponse)
async def pipeline_mode(request: Request) -> PipelineModeResponse:
    """Describe exactly what the real-pipeline developer tool can prove."""

    dependencies, warnings = await _mode(_runtime(request))
    return PipelineModeResponse(
        mode="REAL_QUEUE_PIPELINE",
        proof_scope="GATEWAY_QUEUE_AND_WORKER_RUNTIME_WHEN_WORKER_IS_RUNNING",
        dependencies=dependencies,
        warnings=warnings,
    )


@router.post("/inbound", response_model=EnqueuePipelineMessageResponse)
async def enqueue_pipeline_message(
    payload: EnqueuePipelineMessageRequest,
    request: Request,
) -> EnqueuePipelineMessageResponse:
    """Enqueue a real gateway-shaped message into the configured gateway queue."""

    runtime = _runtime(request)
    message = InboundGatewayMessage(
        request_id=payload.request_id,
        message_id=payload.message_id,
        channel_instance_id=payload.channel_instance_id,
        provider=payload.provider,
        recipient_phone=payload.recipient_phone,
        customer_phone=payload.customer_phone,
        text=payload.text,
        received_at=datetime.now(UTC),
        metadata={"source": "dev.pipeline"},
    )
    delivery_id = await runtime.gateway_queue.enqueue_inbound(message)
    dependencies, warnings = await _mode(runtime)
    mode = (
        "runtime"
        if dependencies["queue"] == "REDIS"
        and dependencies["sessions"] == "REDIS"
        and dependencies["business_registry"] == "POSTGRES"
        else "local"
    )
    return EnqueuePipelineMessageResponse(
        status="accepted",
        delivery_id=delivery_id,
        request_id=payload.request_id,
        mode=mode,
        warnings=warnings,
    )


@router.get("/requests/{request_id}", response_model=PipelineRequestStatusResponse)
async def pipeline_request_status(
    request_id: str,
    request: Request,
) -> PipelineRequestStatusResponse:
    """Inspect queue/dead-letter/audit state for one developer request ID."""

    if not request_id.strip():
        raise HTTPException(status_code=422, detail="request_id must not be empty")
    runtime = _runtime(request)
    snapshot = await runtime.snapshot()
    redis_state = await _redis_request_state(runtime, request_id)
    memory_state = _memory_request_state(runtime, request_id)
    audit_events = await _audit_events(runtime, request_id)
    _dependencies, warnings = await _mode(runtime)
    return PipelineRequestStatusResponse(
        request_id=request_id,
        storage={
            "opened": snapshot.opened,
            "session_backend": snapshot.session_backend,
            "customer_backend": snapshot.customer_backend,
            "business_backend": snapshot.business_backend,
            "gateway_queue_backend": snapshot.gateway_queue_backend,
            "redis_ready": snapshot.redis_ready,
            "postgres_ready": snapshot.postgres_ready,
            "detail": snapshot.detail,
        },
        inbound=tuple(redis_state["inbound"] + memory_state["inbound"]),
        outbound=tuple(redis_state["outbound"] + memory_state["outbound"]),
        inbound_dead_letters=tuple(
            redis_state["inbound_dead_letters"] + memory_state["inbound_dead_letters"]
        ),
        outbound_dead_letters=tuple(
            redis_state["outbound_dead_letters"] + memory_state["outbound_dead_letters"]
        ),
        audit_events=tuple(audit_events),
        warnings=warnings,
    )


async def _redis_request_state(
    runtime: StorageRuntime,
    request_id: str,
) -> dict[str, list[dict[str, object]]]:
    state: dict[str, list[dict[str, object]]] = {
        "inbound": [],
        "outbound": [],
        "inbound_dead_letters": [],
        "outbound_dead_letters": [],
    }
    redis_runtime = runtime.redis_runtime
    if redis_runtime is None:
        return state
    keyspace = RedisKeyspace(runtime.settings.redis_key_prefix, runtime.settings.environment)
    stream_map = {
        "inbound": keyspace.gateway_inbound_stream(),
        "outbound": keyspace.gateway_outbound_stream(),
        "inbound_dead_letters": keyspace.gateway_inbound_dead_letter_stream(),
        "outbound_dead_letters": keyspace.gateway_outbound_dead_letter_stream(),
    }
    for bucket, stream in stream_map.items():
        try:
            entries = await redis_runtime.client.xrevrange(stream, count=200)
        except Exception:
            continue
        for delivery_id, fields in entries:
            record = _stream_record(delivery_id, fields)
            if record.get("request_id") == request_id:
                state[bucket].append(record)
    return state


def _memory_request_state(
    runtime: StorageRuntime,
    request_id: str,
) -> dict[str, list[dict[str, object]]]:
    queue = runtime.gateway_queue
    state: dict[str, list[dict[str, object]]] = {
        "inbound": [],
        "outbound": [],
        "inbound_dead_letters": [],
        "outbound_dead_letters": [],
    }
    for delivery_id, delivery in getattr(queue, "_inbound", {}).items():
        record = _message_record(delivery_id, delivery.message, delivery.attempt)
        if record.get("request_id") == request_id:
            state["inbound"].append(record)
    for delivery_id, delivery in getattr(queue, "_outbound", {}).items():
        record = _message_record(delivery_id, delivery.message, delivery.attempt)
        if record.get("request_id") == request_id:
            state["outbound"].append(record)
    for delivery_id, item in getattr(queue, "inbound_dead_letters", {}).items():
        message, reason = item
        record = _message_record(delivery_id, message, 0)
        if record.get("request_id") == request_id:
            record["reason"] = reason
            state["inbound_dead_letters"].append(record)
    for delivery_id, item in getattr(queue, "outbound_dead_letters", {}).items():
        message, reason = item
        record = _message_record(delivery_id, message, 0)
        if record.get("request_id") == request_id:
            record["reason"] = reason
            state["outbound_dead_letters"].append(record)
    return state


def _stream_record(delivery_id: object, fields: Any) -> dict[str, object]:
    decoded_id = delivery_id.decode() if isinstance(delivery_id, bytes) else str(delivery_id)
    payload = _field(fields, "payload", "{}")
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        data = {"raw_payload": payload}
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    return {
        "delivery_id": decoded_id,
        "request_id": str(data.get("request_id") or ""),
        "message_id": str(data.get("message_id") or data.get("reply_id") or ""),
        "channel_instance_id": str(data.get("channel_instance_id") or ""),
        "business_id": str(data.get("business_id") or ""),
        "recipient_phone": str(data.get("recipient_phone") or ""),
        "customer_phone": str(data.get("customer_phone") or ""),
        "text": str(data.get("text") or ""),
        "attempt": int(_field(fields, "attempt", "0")),
        "reason": _field(fields, "reason", ""),
        "metadata": dict(redact_mapping(metadata)),
    }


def _message_record(delivery_id: str, message: Any, attempt: int) -> dict[str, object]:
    return {
        "delivery_id": delivery_id,
        "request_id": getattr(message, "request_id", ""),
        "message_id": getattr(message, "message_id", getattr(message, "reply_id", "")),
        "channel_instance_id": getattr(message, "channel_instance_id", ""),
        "business_id": getattr(message, "business_id", ""),
        "recipient_phone": getattr(message, "recipient_phone", ""),
        "customer_phone": getattr(message, "customer_phone", ""),
        "text": getattr(message, "text", ""),
        "attempt": attempt,
        "metadata": dict(redact_mapping(getattr(message, "metadata", {}))),
    }


def _field(fields: Any, name: str, default: str = "") -> str:
    value = fields.get(name) if hasattr(fields, "get") else None
    if value is None and hasattr(fields, "get"):
        value = fields.get(name.encode())
    if value is None:
        return default
    return value.decode() if isinstance(value, bytes) else str(value)


async def _audit_events(
    runtime: StorageRuntime,
    request_id: str,
) -> list[dict[str, object]]:
    postgres_runtime = runtime.postgres_runtime
    if postgres_runtime is None:
        return []
    async with postgres_runtime.pool.connection() as connection:
        await connection.execute("SELECT set_config('app.system_maintenance', 'on', true)")
        rows = await connection.execute(
            """
            SELECT event_id, event_type, business_id, severity, conversation_id,
                   message_id, occurred_at, data
            FROM operational_audit_events
            WHERE request_id = %s
            ORDER BY occurred_at ASC, event_id ASC
            LIMIT 100
            """,
            (request_id,),
        )
        return [
            {
                # The production PostgreSQL pool uses dictionary rows.  Indexing
                # them as tuples worked only with tuple-shaped test doubles and
                # caused the real developer status endpoint to return HTTP 500.
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "business_id": row["business_id"],
                "severity": row["severity"],
                "conversation_id": row["conversation_id"],
                "message_id": row["message_id"],
                "occurred_at": row["occurred_at"].isoformat(),
                "data": dict(redact_mapping(row["data"] or {})),
            }
            for row in await rows.fetchall()
        ]


_PIPELINE_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ntheemba Real Pipeline Console</title>
<style nonce="__CSP_NONCE__">
:root{color-scheme:dark;--bg:#07111f;--panel:#0d1b2f;--line:#283e5d;--text:#edf4ff;--muted:#9aadc3;--green:#48d597;--gold:#f4c45d;--blue:#72b7ff}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 10% 0,#183b62 0,transparent 32%),var(--bg);color:var(--text);font:14px/1.45 system-ui,Segoe UI,sans-serif}.shell{min-height:100vh;display:grid;grid-template-rows:auto auto 1fr}.top{display:flex;align-items:center;gap:13px;padding:14px 18px;border-bottom:1px solid var(--line);background:#07111f}h1{font-size:17px;margin:0}.muted{color:var(--muted);font-size:12px}.spacer{flex:1}.pill{border:1px solid var(--line);border-radius:999px;padding:5px 9px;color:var(--muted);font-size:10px;font-weight:800}.link{color:#b9d9ff;font-size:12px}.notice{margin:10px 18px;padding:9px 11px;border:1px solid #715727;border-radius:9px;background:#2a2415;color:#f6d88e;font-size:11px}.workspace{min-height:0;display:grid;grid-template-columns:290px minmax(360px,1fr) 390px}.context,.chat,.inspect{min-height:0;background:rgba(13,27,47,.92)}.context{border-right:1px solid var(--line);padding:14px;overflow:auto}.chat{display:grid;grid-template-rows:auto 1fr auto;border-right:1px solid var(--line)}.inspect{display:grid;grid-template-rows:auto 1fr;overflow:hidden}.panel,.card{border:1px solid var(--line);border-radius:12px;background:var(--panel);padding:12px;margin-bottom:12px}.panel h2,.chat-head h2,.inspect-head h2{font-size:14px;margin:0 0 8px}.field{display:flex;flex-direction:column;gap:5px;margin:10px 0}.field label{color:var(--muted);font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}input,textarea{width:100%;border:1px solid var(--line);border-radius:9px;background:#071321;color:var(--text);padding:9px;outline:none}input:focus,textarea:focus,button:focus-visible,a:focus-visible{outline:3px solid rgba(114,183,255,.45);outline-offset:2px}textarea{resize:none;min-height:52px;max-height:130px}.chat-head,.inspect-head{padding:14px 16px;border-bottom:1px solid var(--line);background:var(--panel)}.chat-head p{margin:3px 0 0}.messages{min-height:0;overflow:auto;padding:18px;display:flex;flex-direction:column;gap:10px}.empty{margin:auto;max-width:300px;text-align:center;color:var(--muted)}.bubble{max-width:78%;padding:10px 12px;border-radius:14px;white-space:pre-wrap;word-break:break-word}.bubble.customer{align-self:flex-end;background:#176d58}.bubble.system{align-self:flex-start;background:#233a5c}.bubble.warning{align-self:center;background:#33273b;color:#e3d5ec;font-size:11px}.bubble .meta{display:block;margin-top:5px;opacity:.68;font-size:9px;text-align:right}.composer{border-top:1px solid var(--line);padding:12px;background:#0b1728}.compose-row{display:grid;grid-template-columns:1fr auto;gap:8px}.primary,.secondary{border:1px solid var(--line);border-radius:9px;padding:9px 11px;font-weight:800;cursor:pointer}.primary{background:linear-gradient(135deg,var(--gold),var(--green));color:#07111f;border:0}.secondary{background:#19304e;color:var(--text)}.buttons{display:flex;gap:7px;flex-wrap:wrap}.inspect-scroll{overflow:auto;padding:12px}.stage{display:grid;grid-template-columns:10px 1fr auto;gap:8px;align-items:center;padding:10px 7px;border-bottom:1px solid #1b3049;font-size:11px}.dot{width:8px;height:8px;border-radius:50%;background:#64758a}.stage.observed .dot{background:var(--green)}.stage.waiting .dot{background:var(--gold)}.stage b{display:block}.stage small,.stage em{color:var(--muted);font-size:10px}.stage em{font-style:normal}.card h3{margin:0 0 7px;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}.details,.mode{white-space:pre-wrap;word-break:break-word;font:10px/1.45 ui-monospace,Consolas,monospace;color:#c4d6e9}@media(max-width:1080px){.workspace{grid-template-columns:270px 1fr}.inspect{grid-column:1/-1;height:560px;border-top:1px solid var(--line)}}@media(max-width:700px){.top .muted,.top .pill{display:none}.workspace{display:block}.context{border-right:0;border-bottom:1px solid var(--line)}.chat{height:680px;border-right:0;border-bottom:1px solid var(--line)}.inspect{height:560px}.notice{margin:8px}}
.search-results{display:grid;gap:7px;margin-top:9px}.product-result{width:100%;text-align:left;border:1px solid var(--line);border-radius:9px;background:#0a1829;color:var(--text);padding:8px;cursor:pointer}.product-result:hover{border-color:var(--blue)}.product-result b,.product-result small{display:block}.product-result small{color:var(--muted);font-size:10px;margin-top:2px}.search-status{color:var(--muted);font-size:11px;margin-top:8px}
</style>
</head>
<body>
<div class="shell"><header class="top"><h1>Ntheemba Real Pipeline Console</h1><span class="muted">Developer-only queue and worker evidence</span><span class="spacer"></span><span class="pill">REAL QUEUE VIEW</span><a class="link" href="/dev/simulator/workspace">Logic simulator workspace</a><a class="link" href="/dev/console">Trace console</a></header><div class="notice">This is a chat-shaped queue probe, not a WhatsApp client. Sending records an inbound message only. The nodes show observed queue, worker, and audit evidence; use the separate logic simulator workspace for in-memory workflow simulation.</div>
<main class="workspace">
<aside class="context">
  <div class="panel">
    <h2>Inbound context</h2>
    <div class="field"><label for="channel">Channel instance ID</label><input id="channel" value="n24-acceptance-wa"></div>
    <div class="field"><label for="customer">Customer phone</label><input id="customer" value="+260955381043"></div>
    <div class="field"><label for="recipient">Recipient phone</label><input id="recipient" value="+260970099024"></div>
  </div>
  <div class="panel"><h2>Find NCPC identity</h2><p class="muted">Published identity only. No price, stock, supplier, policy, barcode, or business result.</p><div class="field"><label for="product-query">What would the customer ask for?</label><input id="product-query" placeholder="e.g. cooking oil"></div><button class="secondary" id="search-products" type="button">Search products</button><div class="search-status" id="product-search-status" aria-live="polite"></div><div class="search-results" id="product-results"></div></div>
  <div class="panel">
    <h2>Mode</h2>
    <pre id="mode">Loading…</pre>
  </div>
</aside>
<section class="chat">
  <div class="chat-head"><h2>Queue conversation</h2><p class="muted" id="conversation-meta">No request queued.</p></div>
  <div class="messages" id="messages" aria-live="polite"><div class="empty">Write a synthetic inbound message. It will appear here and be enqueued for the independently running worker.</div></div>
  <div class="composer"><div class="compose-row"><textarea id="text" aria-label="Synthetic inbound message" placeholder="Write a synthetic inbound message…">Order local relish</textarea><button class="primary" id="send">Enqueue</button></div><div class="buttons" style="margin-top:8px"><button class="secondary" id="refresh">Refresh observed state</button></div></div>
</section>
<aside class="inspect"><div class="inspect-head"><h2>Observed pipeline</h2><span class="muted" id="request-label">No request selected</span></div><div class="inspect-scroll"><div id="pipeline"><div class="empty">Send a message to inspect its real queue evidence.</div></div><div class="card"><h3>Request evidence</h3><div class="details" id="result" aria-live="polite">No request sent yet.</div></div></div></aside>
</main>
</div>
<script nonce="__CSP_NONCE__">
let currentRequestId = '';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','>':'&gt;','<':'&lt;','"':'&quot;',"'":'&#39;'}[char]));
async function fetchJson(url, options = {}) {
  const response = await fetch(url, { ...options, credentials: 'same-origin' });
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}
async function loadMode() {
  $('mode').textContent = JSON.stringify(await fetchJson('/dev/pipeline/mode'), null, 2);
}
function stage(name, detail, state) { return `<div class="stage ${state}"><span class="dot"></span><span><b>${esc(name)}</b><small>${esc(detail)}</small></span><em>${state === 'observed' ? 'observed' : 'waiting'}</em></div>`; }
function renderPipeline(status) { if (!status) return; const inbound=status.inbound||[],outbound=status.outbound||[],audit=status.audit_events||[]; const worker=audit.length||outbound.length; $('pipeline').innerHTML=[stage('Gateway-shaped inbound',inbound.length?`${inbound.length} inbound record(s)`:'No inbound record found',inbound.length?'observed':'waiting'),stage('Queue persistence',status.storage?.gateway_queue_backend?`${status.storage.gateway_queue_backend} queue reported`:'Queue state unavailable',inbound.length?'observed':'waiting'),stage('Inbound worker',worker?'Worker/audit activity observed':'Run the separate inbound worker, then refresh',worker?'observed':'waiting'),stage('Workflow and audit',audit.length?`${audit.length} audit event(s) observed`:'No workflow audit evidence yet',audit.length?'observed':'waiting'),stage('Outbound delivery',outbound.length?`${outbound.length} outbound record(s)`:'No outbound record observed',outbound.length?'observed':'waiting')].join(''); }
function addBubble(role,text,meta='') { const empty=$('messages').querySelector('.empty');if(empty)empty.remove();const node=document.createElement('div');node.className=`bubble ${role}`;node.innerHTML=`${esc(text)}${meta?`<span class="meta">${esc(meta)}</span>`:''}`;$('messages').appendChild(node);$('messages').scrollTop=$('messages').scrollHeight; }
function productDescription(product) { return [product.brand, product.variant, product.size_value && product.size_unit ? `${product.size_value} ${product.size_unit}` : '', product.category].filter(Boolean).join(' · '); }
function showProductResults(products) { $('product-results').innerHTML = products.map(product => `<button class="product-result" type="button" data-product-name="${esc(product.canonical_name)}"><b>${esc(product.canonical_name)}</b><small>${esc(productDescription(product) || 'Published NCPC identity')}</small></button>`).join(''); $('product-results').querySelectorAll('[data-product-name]').forEach(button => button.addEventListener('click', () => { $('text').value = `Do you have ${button.dataset.productName}?`; $('text').focus(); })); }
async function searchProducts() { const query=$('product-query').value.trim(); if(!query) { $('product-search-status').textContent='Enter the product the customer is asking for.'; return; } $('search-products').disabled=true; $('product-search-status').textContent='Searching published NCPC identities…'; $('product-results').innerHTML=''; try { const result=await fetchJson(`/dev/storage/ncpc/products?query=${encodeURIComponent(query)}`); const products=result.results||[]; $('product-search-status').textContent=products.length?`${products.length} identity result(s). Choose one to put it in the chat composer.`:'No published NCPC identity matched that search.'; showProductResults(products); } catch(error) { $('product-search-status').textContent=`Product search failed: ${error.message}`; } finally { $('search-products').disabled=false; } }
async function refresh() {
  if (!currentRequestId) return;
  const status = await fetchJson(`/dev/pipeline/requests/${encodeURIComponent(currentRequestId)}`);
  $('result').textContent = JSON.stringify(status, null, 2);
  $('request-label').textContent = `Request ${currentRequestId}`;
  $('conversation-meta').textContent = `Request ${currentRequestId} — refresh to see worker evidence.`;
  renderPipeline(status);
}
$('send').addEventListener('click', async () => {
  const payload = {
    channel_instance_id: $('channel').value,
    customer_phone: $('customer').value,
    recipient_phone: $('recipient').value,
    text: $('text').value
  };
  try {
    $('send').disabled = true;
    const accepted = await fetchJson('/dev/pipeline/inbound', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    currentRequestId = accepted.request_id;
    addBubble('customer', payload.text, `queued • ${accepted.request_id}`);
    $('text').value = '';
    await refresh();
    if (accepted.warnings?.length) addBubble('warning', accepted.warnings[0], 'runtime warning');
  } catch (error) {
    addBubble('warning', `Request failed: ${error.message}`);
  } finally {
    $('send').disabled = false;
  }
});
$('refresh').addEventListener('click', () => refresh().catch(error => addBubble('warning', `Refresh failed: ${error.message}`)));
$('search-products').addEventListener('click', searchProducts);
$('product-query').addEventListener('keydown', event => { if(event.key === 'Enter') { event.preventDefault(); searchProducts(); } });
$('text').addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); $('send').click(); } });
loadMode().catch(error => { $('mode').textContent = error.message; });
</script>
</body>
</html>
"""


@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def pipeline_console() -> HTMLResponse:
    """Render the local real-pipeline developer console."""

    nonce = token_urlsafe(18)
    html = _PIPELINE_HTML.replace("__CSP_NONCE__", nonce)
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                f"default-src 'none'; style-src 'nonce-{nonce}'; "
                f"script-src 'nonce-{nonce}'; connect-src 'self'; "
                "base-uri 'none'; form-action 'self'; object-src 'none'; "
                "frame-ancestors 'none'"
            ),
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
    )
