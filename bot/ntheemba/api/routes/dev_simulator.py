"""Developer-only conversation simulator API and visual chat console."""

# ruff: noqa: E501

from __future__ import annotations

from secrets import token_urlsafe
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from ntheemba.api.routes.dev_tracing import TraceEventResponse
from ntheemba.application.service import ProcessMessageCommand
from ntheemba.observability.sanitization import redact_mapping
from ntheemba.ports.audit import AuditEvent
from ntheemba.devtools.simulator import (
    DeveloperConversationSimulator,
    SimulatorBusiness,
    SimulatorConversation,
    SimulatorMessageResult,
    SimulatorSessionSnapshot,
)

router = APIRouter(
    prefix="/dev/simulator",
    tags=["developer-simulator"],
    include_in_schema=False,
)


class SimulatorBusinessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    business_id: str
    name: str
    description: str
    suggested_messages: tuple[str, ...]
    group: str = "standard"
    adapter_type: str = "tradeflow_standard"
    channel_instance_id: str = ""
    phone_e164: str = ""
    capabilities: tuple[str, ...] = ()


class SimulatorConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: str
    business_id: str
    channel_instance_id: str
    customer_phone: str
    customer_name: str
    title: str
    scenario_group: str
    status: str
    suggested_messages: tuple[str, ...]
    latest_message: str


class SimulatorReplyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message_id: str
    kind: str
    text: str
    image_url: str
    caption: str


class SimulatorSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exists: bool
    conversation_id: str
    business_id: str
    customer_id: str
    flow: str
    stage: str
    mode: str
    status: str
    handover_status: str
    revision: int
    pending_prompt: str
    selected_product: str
    quantity: int | None
    fulfilment_method: str
    selected_service: str
    selected_date: str
    selected_time: str
    selected_staff: str
    customer_name: str
    contact_number: str
    submitted_request_id: str
    history: tuple[dict[str, str], ...]


class SendSimulatorMessageRequest(BaseModel):
    business_id: Annotated[str, Field(min_length=1, max_length=100)]
    customer_id: Annotated[str, Field(min_length=1, max_length=100)]
    text: Annotated[str, Field(min_length=1, max_length=4000)]
    message_id: Annotated[str, Field(min_length=1, max_length=160)] = Field(
        default_factory=lambda: f"SIM-{uuid4()}"
    )
    request_id: Annotated[str, Field(min_length=1, max_length=160)] = Field(
        default_factory=lambda: f"REQ-SIM-{uuid4()}"
    )


class SendWorkspaceMessageRequest(BaseModel):
    conversation_id: Annotated[str, Field(min_length=1, max_length=160)]
    text: Annotated[str, Field(min_length=1, max_length=4000)]
    message_id: Annotated[str, Field(min_length=1, max_length=160)] = Field(
        default_factory=lambda: f"SIM-{uuid4()}"
    )
    request_id: Annotated[str, Field(min_length=1, max_length=160)] = Field(
        default_factory=lambda: f"REQ-SIM-{uuid4()}"
    )




class CapabilityDefinitionResponse(BaseModel):
    capability: str
    title: str
    description: str
    workflow_ids: tuple[str, ...]
    tradeflow_operations: tuple[str, ...]


class UnsupportedObservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: str
    value: str
    business_id: str
    adapter_type: str
    observed_at: str
    source: str


class SimulatorAuditEventResponse(BaseModel):
    event_id: str
    event_type: str
    request_id: str
    business_id: str
    severity: str
    conversation_id: str
    message_id: str
    occurred_at: str
    data: dict[str, object]

    @classmethod
    def from_event(cls, event: AuditEvent) -> "SimulatorAuditEventResponse":
        return cls(
            event_id=event.event_id,
            event_type=event.event_type,
            request_id=event.request_id,
            business_id=event.business_id,
            severity=event.severity.value,
            conversation_id=event.conversation_id,
            message_id=event.message_id,
            occurred_at=event.occurred_at.isoformat(),
            data=dict(redact_mapping(event.data)),
        )


class SimulatorMessageResponse(BaseModel):
    status: str
    request_id: str
    conversation_id: str
    published_message_ids: tuple[str, ...]
    error_code: str
    trace_id: str
    replies: tuple[SimulatorReplyResponse, ...]
    session: SimulatorSessionResponse


class ReplaySimulatorMessageRequest(BaseModel):
    same_message_id: bool = True


class SimulatorActionResponse(BaseModel):
    status: Literal["reset", "expired"]


def _simulator(request: Request) -> DeveloperConversationSimulator:
    simulator = getattr(request.app.state, "conversation_simulator", None)
    if not isinstance(simulator, DeveloperConversationSimulator):
        raise HTTPException(status_code=503, detail="Conversation simulator unavailable")
    return simulator


def _session_response(session: SimulatorSessionSnapshot) -> SimulatorSessionResponse:
    return SimulatorSessionResponse.model_validate(session)


def _message_response(result: SimulatorMessageResult) -> SimulatorMessageResponse:
    return SimulatorMessageResponse(
        status=result.outcome.status.value,
        request_id=result.outcome.request_id,
        conversation_id=result.outcome.conversation_id,
        published_message_ids=result.outcome.published_message_ids,
        error_code=result.outcome.error_code,
        trace_id=result.trace_id,
        replies=tuple(SimulatorReplyResponse.model_validate(reply) for reply in result.replies),
        session=_session_response(result.session),
    )


@router.get("/businesses", response_model=list[SimulatorBusinessResponse])
async def list_simulator_businesses(request: Request) -> list[SimulatorBusinessResponse]:
    businesses: tuple[SimulatorBusiness, ...] = _simulator(request).businesses
    return [SimulatorBusinessResponse.model_validate(business) for business in businesses]


@router.post("/messages", response_model=SimulatorMessageResponse)
async def send_simulator_message(
    payload: SendSimulatorMessageRequest,
    request: Request,
) -> SimulatorMessageResponse:
    command = ProcessMessageCommand(
        business_id=payload.business_id,
        customer_id=payload.customer_id,
        message_id=payload.message_id,
        text=payload.text,
        whatsapp_session_id="developer-simulator",
        request_id=payload.request_id,
    )
    try:
        result = await _simulator(request).send_message(command)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Unknown simulator business") from error
    return _message_response(result)


@router.get(
    "/workspace/businesses",
    response_model=list[SimulatorBusinessResponse],
)
async def list_workspace_businesses(
    request: Request,
) -> list[SimulatorBusinessResponse]:
    return [
        SimulatorBusinessResponse.model_validate(business)
        for business in _simulator(request).workspace_businesses
    ]


@router.get(
    "/workspace/conversations",
    response_model=list[SimulatorConversationResponse],
)
async def list_workspace_conversations(
    request: Request,
) -> list[SimulatorConversationResponse]:
    conversations: tuple[SimulatorConversation, ...] = (
        _simulator(request).workspace_conversations
    )
    return [
        SimulatorConversationResponse.model_validate(conversation)
        for conversation in conversations
    ]


@router.post(
    "/workspace/messages",
    response_model=SimulatorMessageResponse,
)
async def send_workspace_message(
    payload: SendWorkspaceMessageRequest,
    request: Request,
) -> SimulatorMessageResponse:
    try:
        result = await _simulator(request).send_workspace_message(
            payload.conversation_id,
            payload.text,
            message_id=payload.message_id,
            request_id=payload.request_id,
        )
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail="Unknown simulator conversation or channel",
        ) from error
    return _message_response(result)


@router.get(
    "/workspace/conversations/{conversation_id}",
    response_model=SimulatorSessionResponse,
)
async def get_workspace_conversation(
    conversation_id: str,
    request: Request,
) -> SimulatorSessionResponse:
    return _session_response(
        await _simulator(request).get_workspace_session(conversation_id)
    )


@router.delete(
    "/workspace/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def reset_workspace_conversation(
    conversation_id: str,
    request: Request,
) -> Response:
    await _simulator(request).reset_workspace_conversation(conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)




@router.get(
    "/workspace/capabilities",
    response_model=list[CapabilityDefinitionResponse],
)
async def list_workspace_capabilities(
    request: Request,
) -> list[CapabilityDefinitionResponse]:
    return [
        CapabilityDefinitionResponse(
            capability=definition.capability.value,
            title=definition.title,
            description=definition.description,
            workflow_ids=definition.workflow_ids,
            tradeflow_operations=definition.tradeflow_operations,
        )
        for definition in _simulator(request).canonical_capabilities
    ]


@router.get(
    "/workspace/unsupported",
    response_model=list[UnsupportedObservationResponse],
)
async def list_workspace_unsupported(
    request: Request,
) -> list[UnsupportedObservationResponse]:
    observations = await _simulator(request).unsupported_observations()
    return [
        UnsupportedObservationResponse(
            kind=observation.kind.value,
            value=observation.value,
            business_id=observation.business_id,
            adapter_type=observation.adapter_type,
            observed_at=observation.observed_at.isoformat(),
            source=observation.source,
        )
        for observation in observations
    ]


@router.get(
    "/audit",
    response_model=list[SimulatorAuditEventResponse],
)
async def list_simulator_audit_events(
    request: Request,
) -> list[SimulatorAuditEventResponse]:
    events = await _simulator(request).audit_events()
    return [SimulatorAuditEventResponse.from_event(event) for event in events]


@router.get(
    "/requests/{request_id}/trace",
    response_model=list[TraceEventResponse],
)
async def get_simulator_request_trace(
    request_id: str,
    request: Request,
) -> list[TraceEventResponse]:
    events = await _simulator(request).trace_for_request(request_id)
    return [TraceEventResponse.from_event(event) for event in events]


@router.get(
    "/conversations/{business_id}/{customer_id}",
    response_model=SimulatorSessionResponse,
)
async def get_simulator_conversation(
    business_id: str,
    customer_id: str,
    request: Request,
) -> SimulatorSessionResponse:
    session = await _simulator(request).get_session(business_id, customer_id)
    return _session_response(session)


@router.delete(
    "/conversations/{business_id}/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def reset_simulator_conversation(
    business_id: str,
    customer_id: str,
    request: Request,
) -> Response:
    await _simulator(request).reset_conversation(business_id, customer_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/conversations/{business_id}/{customer_id}/expire",
    response_model=SimulatorActionResponse,
)
async def expire_simulator_conversation(
    business_id: str,
    customer_id: str,
    request: Request,
) -> SimulatorActionResponse:
    await _simulator(request).expire_conversation(business_id, customer_id)
    return SimulatorActionResponse(status="expired")


@router.post(
    "/conversations/{business_id}/{customer_id}/replay",
    response_model=SimulatorMessageResponse,
)
async def replay_simulator_message(
    business_id: str,
    customer_id: str,
    payload: ReplaySimulatorMessageRequest,
    request: Request,
) -> SimulatorMessageResponse:
    try:
        result = await _simulator(request).replay_last(
            business_id,
            customer_id,
            same_message_id=payload.same_message_id,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return _message_response(result)


_SIMULATOR_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ntheemba Conversation Simulator</title>
<style nonce="__CSP_NONCE__">
:root{color-scheme:dark;--bg:#07111f;--panel:#0d1a2c;--panel2:#12223a;--line:#263a56;--text:#edf4ff;--muted:#91a5bf;--accent:#38d996;--accent2:#56a8ff;--warn:#ffc857;--bad:#ff6577;--bubble:#164b3d;--assistant:#172944}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 15% 0,#132c47 0,transparent 36%),var(--bg);color:var(--text);font:14px/1.45 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
button,input,select,textarea{font:inherit}.app{min-height:100vh;display:grid;grid-template-rows:auto 1fr}.topbar{display:flex;gap:12px;align-items:center;padding:13px 18px;border-bottom:1px solid var(--line);background:rgba(7,17,31,.9);backdrop-filter:blur(12px);position:sticky;top:0;z-index:5}.brand{font-weight:800;font-size:16px;letter-spacing:.2px}.brand span{color:var(--accent)}.topbar .spacer{flex:1}.badge{padding:5px 9px;border:1px solid var(--line);border-radius:999px;color:var(--muted);font-size:12px}.link{color:var(--accent2);text-decoration:none}
.workspace{display:grid;grid-template-columns:minmax(360px,43%) minmax(420px,57%);min-height:0;height:calc(100vh - 58px)}.chat-pane,.inspect-pane{min-height:0}.chat-pane{display:grid;grid-template-rows:auto auto 1fr auto;border-right:1px solid var(--line);background:rgba(8,19,33,.82)}.controls{padding:13px;border-bottom:1px solid var(--line);display:grid;grid-template-columns:1fr 1fr;gap:9px}.field{display:flex;flex-direction:column;gap:5px}.field label{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}select,input,textarea{width:100%;color:var(--text);background:#081522;border:1px solid var(--line);border-radius:9px;padding:9px 10px;outline:none}select:focus,input:focus,textarea:focus{border-color:var(--accent2);box-shadow:0 0 0 3px rgba(86,168,255,.12)}.quick{padding:9px 13px;border-bottom:1px solid var(--line);display:flex;gap:7px;overflow:auto}.chip{white-space:nowrap;background:transparent;color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:6px 9px;cursor:pointer}.chip:hover{border-color:var(--accent2);color:var(--text)}
.messages{padding:18px;overflow:auto;display:flex;flex-direction:column;gap:12px}.empty-chat{margin:auto;color:var(--muted);text-align:center;max-width:280px}.bubble{max-width:82%;padding:10px 12px;border-radius:14px;box-shadow:0 5px 18px rgba(0,0,0,.15);white-space:pre-wrap;word-break:break-word}.bubble.customer{align-self:flex-end;background:var(--bubble);border-bottom-right-radius:4px}.bubble.assistant{align-self:flex-start;background:var(--assistant);border-bottom-left-radius:4px}.bubble.system{align-self:center;max-width:94%;background:#2a2134;color:#d7c9e8;font-size:12px}.bubble .meta{display:block;margin-top:5px;color:#b5c7d9;font-size:10px;text-align:right}.composer{padding:12px;border-top:1px solid var(--line);display:grid;grid-template-columns:1fr auto;gap:9px;background:var(--panel)}textarea{resize:none;min-height:48px;max-height:130px}.primary,.secondary,.danger{border:0;border-radius:9px;padding:9px 13px;cursor:pointer;font-weight:700}.primary{background:var(--accent);color:#042017}.secondary{background:#203450;color:var(--text)}.danger{background:#4a2430;color:#ffdce1}.primary:disabled{opacity:.55;cursor:wait}
.inspect-pane{display:grid;grid-template-rows:minmax(0,62%) minmax(0,38%);background:rgba(10,20,35,.9)}.pipeline-section,.session-section{min-height:0;display:grid;grid-template-rows:auto 1fr}.section-head{display:flex;align-items:center;gap:9px;padding:12px 14px;border-bottom:1px solid var(--line);background:var(--panel)}.section-head h2{margin:0;font-size:14px}.section-head .spacer{flex:1}.muted{color:var(--muted);font-size:12px}.actions{display:flex;gap:7px}.actions button{padding:6px 9px;font-size:12px}.pipeline{overflow:auto;padding:13px}.stage{display:grid;grid-template-columns:24px minmax(160px,1fr) 90px 22px;align-items:center;gap:8px;padding:9px 10px;border:1px solid var(--line);border-radius:10px;background:var(--panel);margin-bottom:8px;cursor:pointer}.stage:hover{border-color:#38577c}.dot{width:12px;height:12px;border-radius:50%;border:2px solid #60738d}.stage.running .dot{border-color:var(--warn);border-top-color:transparent;animation:spin .8s linear infinite}.stage.passed .dot{background:var(--accent);border-color:var(--accent)}.stage.failed .dot{background:var(--bad);border-color:var(--bad)}.stage.skipped .dot{background:#667085;border-color:#667085}.stage .node{font-weight:700}.stage .component{display:block;color:var(--muted);font-size:11px}.duration{text-align:right;color:var(--muted);font-variant-numeric:tabular-nums}.chev{color:var(--muted)}.detail{display:none;grid-column:2/-1;margin-top:7px;padding:9px;background:#071321;border-radius:7px;color:#b9c9dd;white-space:pre-wrap;font:11px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace}.stage.open .detail{display:block}.trace-meta{padding:0 2px 9px;color:var(--muted);font-size:11px}.session-body{overflow:auto;padding:12px;display:grid;grid-template-columns:1fr 1fr;gap:9px}.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px}.card h3{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:0 0 8px}.kv{display:grid;grid-template-columns:115px 1fr;gap:5px;font-size:12px}.kv span:nth-child(odd){color:var(--muted)}.history{grid-column:1/-1;max-height:160px;overflow:auto}.history-row{display:grid;grid-template-columns:70px 1fr;gap:8px;padding:5px 0;border-bottom:1px solid rgba(38,58,86,.65)}.history-row:last-child{border:0}.json{white-space:pre-wrap;word-break:break-word;font:11px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace;color:#bdd0e5}
.toast{position:fixed;right:18px;bottom:18px;background:#172944;border:1px solid var(--line);padding:10px 13px;border-radius:9px;box-shadow:0 10px 30px rgba(0,0,0,.35);display:none;z-index:10}.toast.show{display:block}.toast.bad{border-color:var(--bad)}@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:900px){.workspace{grid-template-columns:1fr;height:auto}.chat-pane{height:75vh;border-right:0;border-bottom:1px solid var(--line)}.inspect-pane{height:90vh}.controls{grid-template-columns:1fr}.session-body{grid-template-columns:1fr}.history{grid-column:auto}}
</style>
</head>
<body>
<div class="app">
<header class="topbar"><div class="brand">Ntheemba <span>Conversation Simulator</span></div><div class="badge">Developer only</div><div class="spacer"></div><a class="link" href="/dev/console">Observability console</a></header>
<main class="workspace">
<section class="chat-pane">
  <div class="controls">
    <div class="field"><label>Business</label><select id="business"></select></div>
    <div class="field"><label>Simulated customer ID</label><input id="customer" value="260970000001" maxlength="100"></div>
  </div>
  <div class="quick" id="quick"></div>
  <div class="messages" id="messages"><div class="empty-chat">Choose a suggested message or type below. Every message runs through the real Ntheemba application pipeline.</div></div>
  <div class="composer"><textarea id="message" placeholder="Type a customer message…"></textarea><button class="primary" id="send">Send</button></div>
</section>
<section class="inspect-pane">
  <div class="pipeline-section">
    <div class="section-head"><h2>Message pipeline</h2><span class="muted" id="trace-label">No trace yet</span><div class="spacer"></div><span class="badge" id="request-status">idle</span></div>
    <div class="pipeline" id="pipeline"></div>
  </div>
  <div class="session-section">
    <div class="section-head"><h2>Session inspector</h2><span class="muted" id="conversation-label">No active session</span><div class="spacer"></div><div class="actions"><button class="secondary" id="replay-new">Replay new ID</button><button class="secondary" id="replay-same">Replay same ID</button><button class="secondary" id="expire">Expire</button><button class="danger" id="reset">Reset</button></div></div>
    <div class="session-body" id="session"></div>
  </div>
</section>
</main>
</div>
<div class="toast" id="toast"></div>
<script nonce="__CSP_NONCE__">
const pipelineOrder=['message.process','message.deduplicate','session.open','message.interpret','workflow.route','transition.validate','workflow.execute','session.commit','reply.publish','message.release_claim'];
const businessEl=document.getElementById('business'),customerEl=document.getElementById('customer'),messageEl=document.getElementById('message'),messagesEl=document.getElementById('messages'),pipelineEl=document.getElementById('pipeline'),sessionEl=document.getElementById('session'),sendEl=document.getElementById('send'),quickEl=document.getElementById('quick'),toastEl=document.getElementById('toast');
let businesses=[];let activeRequest='';let lastTrace=[];let polling=false;
function esc(value){return String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}
async function api(url,options={}){const response=await fetch(url,{...options,credentials:'same-origin'});if(!response.ok){let detail=`${response.status} ${response.statusText}`;try{const body=await response.json();detail=typeof body.detail==='string'?body.detail:JSON.stringify(body.detail);}catch(_){ }throw new Error(detail);}if(response.status===204)return null;return response.json();}
function toast(text,bad=false){toastEl.textContent=text;toastEl.className=`toast show${bad?' bad':''}`;setTimeout(()=>toastEl.className='toast',2600);}
function ids(){return{business:businessEl.value,customer:customerEl.value.trim()};}
function addBubble(role,text,meta=''){const empty=messagesEl.querySelector('.empty-chat');if(empty)empty.remove();const div=document.createElement('div');div.className=`bubble ${role}`;div.innerHTML=`${esc(text)}${meta?`<span class="meta">${esc(meta)}</span>`:''}`;messagesEl.appendChild(div);messagesEl.scrollTop=messagesEl.scrollHeight;}
function quickMessages(){const business=businesses.find(item=>item.business_id===businessEl.value);quickEl.innerHTML=(business?.suggested_messages||[]).map(text=>`<button class="chip" data-message="${esc(text)}">${esc(text)}</button>`).join('');quickEl.querySelectorAll('[data-message]').forEach(button=>button.addEventListener('click',()=>{messageEl.value=button.dataset.message;messageEl.focus();}));}
function grouped(events){const map=new Map();for(const event of events){const previous=map.get(event.span_id);if(!previous||event.status!=='running')map.set(event.span_id,event);}return [...map.values()];}
function renderPipeline(events=lastTrace,forceWaiting=false){lastTrace=events;const finals=grouped(events);const byNode=new Map(finals.map(event=>[event.node_id,event]));const dynamic=finals.filter(event=>!pipelineOrder.includes(event.node_id));const nodes=[...pipelineOrder,...dynamic.map(event=>event.node_id)];pipelineEl.innerHTML=`<div class="trace-meta">${activeRequest?`Request: ${esc(activeRequest)}`:'Send a message to create a trace.'}</div>`+nodes.map(node=>{const event=byNode.get(node);const status=event?.status||(forceWaiting?'waiting':'waiting');const duration=event?.duration_ms==null?'—':`${Number(event.duration_ms).toFixed(2)} ms`;const detail=event?JSON.stringify({span_id:event.span_id,parent_span_id:event.parent_span_id,component:event.component,attributes:event.attributes,error_type:event.error_type,error_message:event.error_message},null,2):'Waiting for this stage.';return `<div class="stage ${esc(status)}"><span class="dot"></span><div><span class="node">${esc(node)}</span><span class="component">${esc(event?.component||'not reached')}</span></div><span class="duration">${duration}</span><span class="chev">⌄</span><div class="detail">${esc(detail)}</div></div>`;}).join('');pipelineEl.querySelectorAll('.stage').forEach(stage=>stage.addEventListener('click',()=>stage.classList.toggle('open')));const traceId=events[0]?.trace_id||'';document.getElementById('trace-label').textContent=traceId||'No trace yet';}
function renderSession(session){const label=document.getElementById('conversation-label');if(!session?.exists){label.textContent='No active session';sessionEl.innerHTML='<div class="card"><h3>State</h3><div class="muted">A session will be created after the first accepted message.</div></div>';return;}label.textContent=session.conversation_id;const fields=[['Flow',session.flow],['Stage',session.stage],['Mode',session.mode],['Status',session.status],['Revision',session.revision],['Pending',session.pending_prompt||'—'],['Product',session.selected_product||'—'],['Quantity',session.quantity??'—'],['Fulfilment',session.fulfilment_method||'—'],['Service',session.selected_service||'—'],['Date',session.selected_date||'—'],['Time',session.selected_time||'—'],['Staff',session.selected_staff||'—'],['Customer',session.customer_name||'—'],['Contact',session.contact_number||'—'],['Submission',session.submitted_request_id||'—']];sessionEl.innerHTML=`<div class="card"><h3>Current workflow</h3><div class="kv">${fields.map(([k,v])=>`<span>${esc(k)}</span><span>${esc(v)}</span>`).join('')}</div></div><div class="card"><h3>Raw safe snapshot</h3><div class="json">${esc(JSON.stringify({...session,history:undefined},null,2))}</div></div><div class="card history"><h3>Recent conversation history</h3>${session.history.length?session.history.map(turn=>`<div class="history-row"><strong>${esc(turn.role)}</strong><span>${esc(turn.text)}</span></div>`).join(''):'<div class="muted">No turns retained.</div>'}</div>`;}
async function pollTrace(requestId){polling=true;while(polling&&activeRequest===requestId){try{const events=await api(`/dev/simulator/requests/${encodeURIComponent(requestId)}/trace`);if(events.length)renderPipeline(events,true);}catch(_){ }await new Promise(resolve=>setTimeout(resolve,120));}}
async function send(){const text=messageEl.value.trim();const {business,customer}=ids();if(!text||!business||!customer)return;messageEl.value='';const requestId=`REQ-SIM-${crypto.randomUUID()}`,messageId=`SIM-${crypto.randomUUID()}`;activeRequest=requestId;sendEl.disabled=true;document.getElementById('request-status').textContent='processing';renderPipeline([],true);addBubble('customer',text,messageId.slice(0,18));const pollingTask=pollTrace(requestId);try{const result=await api('/dev/simulator/messages',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({business_id:business,customer_id:customer,text,message_id:messageId,request_id:requestId})});polling=false;await pollingTask;const events=await api(`/dev/simulator/requests/${encodeURIComponent(requestId)}/trace`);renderPipeline(events);renderSession(result.session);document.getElementById('request-status').textContent=result.status;for(const reply of result.replies){addBubble('assistant',reply.text||reply.caption||`[${reply.kind}]`,reply.message_id.slice(0,18));}if(!result.replies.length)addBubble('system',`No bot reply published. Processing status: ${result.status}.`);if(result.error_code)toast(result.error_code,true);}catch(error){polling=false;await pollingTask;document.getElementById('request-status').textContent='request failed';addBubble('system',`Simulator request failed: ${error.message}`);toast(error.message,true);}finally{sendEl.disabled=false;messageEl.focus();}}
async function loadSession(){const {business,customer}=ids();if(!business||!customer)return;try{renderSession(await api(`/dev/simulator/conversations/${encodeURIComponent(business)}/${encodeURIComponent(customer)}`));}catch(error){toast(error.message,true);}}
async function replay(same){const {business,customer}=ids();activeRequest='';document.getElementById('request-status').textContent='replaying';try{const result=await api(`/dev/simulator/conversations/${encodeURIComponent(business)}/${encodeURIComponent(customer)}/replay`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({same_message_id:same})});activeRequest=result.request_id;const events=await api(`/dev/simulator/requests/${encodeURIComponent(result.request_id)}/trace`);renderPipeline(events);renderSession(result.session);document.getElementById('request-status').textContent=result.status;addBubble('system',same?'Replayed the last inbound message with the same message ID.':'Replayed the last text with a new message ID.');for(const reply of result.replies)addBubble('assistant',reply.text||reply.caption,reply.message_id.slice(0,18));}catch(error){toast(error.message,true);}}
async function reset(){const {business,customer}=ids();if(!confirm('Reset this simulated conversation and release its message IDs?'))return;await api(`/dev/simulator/conversations/${encodeURIComponent(business)}/${encodeURIComponent(customer)}`,{method:'DELETE'});messagesEl.innerHTML='<div class="empty-chat">Conversation reset. Send another message to create a fresh session.</div>';lastTrace=[];activeRequest='';renderPipeline();renderSession(null);document.getElementById('request-status').textContent='reset';}
async function expire(){const {business,customer}=ids();await api(`/dev/simulator/conversations/${encodeURIComponent(business)}/${encodeURIComponent(customer)}/expire`,{method:'POST'});addBubble('system','Session expired. The next accepted message creates a new conversation session.');await loadSession();}
async function init(){businesses=await api('/dev/simulator/businesses');businessEl.innerHTML=businesses.map(item=>`<option value="${esc(item.business_id)}">${esc(item.name)}</option>`).join('');quickMessages();renderPipeline();renderSession(null);}
businessEl.addEventListener('change',()=>{quickMessages();loadSession();});customerEl.addEventListener('change',loadSession);sendEl.addEventListener('click',send);messageEl.addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();send();}});document.getElementById('reset').addEventListener('click',()=>reset().catch(error=>toast(error.message,true)));document.getElementById('expire').addEventListener('click',()=>expire().catch(error=>toast(error.message,true)));document.getElementById('replay-same').addEventListener('click',()=>replay(true));document.getElementById('replay-new').addEventListener('click',()=>replay(false));init().catch(error=>toast(`Initialization failed: ${error.message}`,true));
</script>
</body>
</html>"""


@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def conversation_simulator_console() -> HTMLResponse:
    """Render the protected developer conversation simulator."""

    nonce = token_urlsafe(18)
    html = _SIMULATOR_HTML.replace("__CSP_NONCE__", nonce)
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                f"default-src 'none'; style-src 'nonce-{nonce}'; "
                f"script-src 'nonce-{nonce}'; connect-src 'self'; "
                "img-src 'self' data: https:; base-uri 'none'; form-action 'none'; "
                "frame-ancestors 'none'"
            ),
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
    )


_WORKSPACE_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ntheemba Multi-Conversation Simulator</title>
<style nonce="__CSP_NONCE__">
:root{color-scheme:dark;--bg:#07111f;--panel:#0d1b2f;--panel2:#12243d;--line:#253b59;--text:#eef5ff;--muted:#91a5bf;--green:#38d39f;--gold:#f0bf56;--red:#ff6b72;--blue:#60a5fa}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 10% 0,#15365b 0,transparent 34%),var(--bg);color:var(--text);font:14px/1.45 Inter,ui-sans-serif,system-ui,sans-serif;overflow:hidden}.shell{height:100vh;display:grid;grid-template-rows:auto 1fr}.top{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:14px 18px;border-bottom:1px solid var(--line);background:rgba(7,17,31,.92)}.brand h1{font-size:17px;margin:0}.brand p{margin:2px 0 0;color:var(--muted);font-size:12px}.top-actions{display:flex;gap:8px;align-items:center}.pill{border:1px solid var(--line);border-radius:999px;padding:5px 10px;color:var(--muted);font-size:11px}.workspace{min-height:0;display:grid;grid-template-columns:310px minmax(360px,1fr) 430px}.inbox,.chat,.inspect{min-height:0;background:rgba(13,27,47,.94)}.inbox{border-right:1px solid var(--line);overflow:auto}.chat{display:grid;grid-template-rows:auto 1fr auto;border-right:1px solid var(--line)}.inspect{display:grid;grid-template-rows:auto 1fr;overflow:hidden}.section-title{position:sticky;top:0;z-index:3;padding:14px 16px;background:rgba(13,27,47,.98);border-bottom:1px solid var(--line)}.section-title strong{display:block}.section-title span{color:var(--muted);font-size:11px}.group{padding:12px 10px 4px;color:var(--gold);font-size:10px;font-weight:900;letter-spacing:.12em;text-transform:uppercase}.business-label{padding:8px 12px;color:#cbdaf0;font-size:12px;font-weight:800}.conversation{width:calc(100% - 14px);margin:0 7px 6px;padding:11px;border:1px solid transparent;border-radius:12px;background:transparent;color:inherit;text-align:left;cursor:pointer}.conversation:hover{background:#11233c}.conversation.active{background:#17304f;border-color:#36587f}.conversation-row{display:flex;justify-content:space-between;gap:8px}.conversation b{font-size:13px}.conversation small{color:var(--muted)}.conversation p{margin:5px 0 0;color:#b6c8dd;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.chat-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;padding:14px 16px;border-bottom:1px solid var(--line)}.chat-head h2{margin:0;font-size:16px}.chat-head p{margin:3px 0 0;color:var(--muted);font-size:11px}.buttons{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}button{border:1px solid var(--line);background:#152a46;color:var(--text);padding:8px 11px;border-radius:9px;font-weight:750;cursor:pointer}button:hover{border-color:#4b6d96}button.primary{background:linear-gradient(135deg,var(--gold),var(--green));color:#07111f;border:0}button.danger{color:#ffd2d4;border-color:#7f3540}.messages{min-height:0;overflow:auto;padding:18px;display:flex;flex-direction:column;gap:10px}.empty{margin:auto;color:var(--muted);text-align:center;max-width:300px}.bubble{max-width:76%;padding:10px 12px;border-radius:13px;white-space:pre-wrap}.bubble.customer{align-self:flex-end;background:#176b57}.bubble.assistant{align-self:flex-start;background:#1c3658}.bubble.system{align-self:center;background:#2c2538;color:#d9cbe7;font-size:11px}.bubble .meta{display:block;margin-top:5px;opacity:.65;font-size:9px}.composer{border-top:1px solid var(--line);padding:10px 12px;background:#0b1728}.chips{display:flex;gap:6px;overflow:auto;padding-bottom:8px}.chip{white-space:nowrap;padding:6px 9px;font-size:10px;background:#101f35}.compose-row{display:grid;grid-template-columns:1fr auto;gap:8px}textarea{width:100%;resize:none;min-height:44px;max-height:120px;border:1px solid var(--line);border-radius:10px;background:#071321;color:var(--text);padding:10px;outline:none}.tabs{display:flex;border-bottom:1px solid var(--line)}.tab{flex:1;border:0;border-radius:0;background:transparent;color:var(--muted)}.tab.active{color:var(--text);border-bottom:2px solid var(--green)}.inspect-scroll{overflow:auto;padding:12px}.card{border:1px solid var(--line);border-radius:12px;background:#0b182a;padding:12px;margin-bottom:10px}.card h3{font-size:12px;margin:0 0 9px}.kv{display:grid;grid-template-columns:125px 1fr;gap:6px 10px;font-size:11px}.kv span:nth-child(odd){color:var(--muted)}.capabilities{display:flex;flex-wrap:wrap;gap:5px}.cap{border:1px solid #2d5671;border-radius:999px;padding:4px 7px;font-size:9px;color:#bfe8dc}.stage{display:grid;grid-template-columns:10px 1fr auto;gap:8px;align-items:center;padding:8px;border-bottom:1px solid #172a43;font-size:10px}.dot{width:7px;height:7px;border-radius:50%;background:#53677f}.passed .dot{background:var(--green)}.failed .dot{background:var(--red)}.running .dot{background:var(--gold)}.stage em{font-style:normal;color:var(--muted)}.history-row{display:grid;grid-template-columns:62px 1fr;gap:8px;padding:7px 0;border-bottom:1px solid #172a43;font-size:10px}.history-row strong{color:var(--green)}.notice{padding:9px;border:1px solid #5f4b22;border-radius:9px;color:#f5d68d;background:#2b2514;font-size:10px}@media(max-width:1050px){body{overflow:auto}.shell{height:auto}.workspace{grid-template-columns:280px 1fr}.inspect{grid-column:1/-1;height:700px;border-top:1px solid var(--line)}}@media(max-width:720px){.workspace{display:block}.inbox{height:360px}.chat{height:720px}.inspect{height:720px}.top{align-items:flex-start}.top-actions{display:none}}
</style>
</head>
<body>
<div class="shell">
<header class="top"><div class="brand"><h1>Ntheemba Multi-Conversation Simulator</h1><p>One capability-neutral bot • business selected by receiving channel • multiple isolated sessions</p></div><div class="top-actions"><span class="pill" id="business-count">0 businesses</span><span class="pill" id="conversation-count">0 conversations</span><a href="/dev/simulator"><button>Classic simulator</button></a></div></header>
<main class="workspace">
<aside class="inbox"><div class="section-title"><strong>Conversation examples</strong><span>Standard and customised TradeFlow channels</span></div><div id="inbox-list"></div></aside>
<section class="chat"><div class="chat-head"><div><h2 id="chat-name">Select a conversation</h2><p id="chat-meta">The receiving business channel activates the capability profile.</p></div><div class="buttons"><button id="run-example">Run example</button><button id="reset" class="danger">Reset</button></div></div><div class="messages" id="messages"><div class="empty">Select any seeded conversation. Each card keeps its own business-and-customer session.</div></div><div class="composer"><div class="chips" id="chips"></div><div class="compose-row"><textarea id="message" placeholder="Type a customer message..."></textarea><button class="primary" id="send">Send</button></div></div></section>
<aside class="inspect"><div class="tabs"><button class="tab active" data-tab="context">Context</button><button class="tab" data-tab="pipeline">Pipeline</button><button class="tab" data-tab="session">Session</button></div><div class="inspect-scroll" id="inspect-content"></div></aside>
</main></div>
<script nonce="__CSP_NONCE__">
const state={businesses:[],conversations:[],active:null,lastTrace:[],tab:'context'};const $=id=>document.getElementById(id);const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));async function api(path,options){const response=await fetch(path,options);if(!response.ok){let detail=response.statusText;try{const body=await response.json();detail=body.detail||body.error?.message||detail}catch(_){}throw new Error(detail)}if(response.status===204)return null;return response.json()}function business(id){return state.businesses.find(item=>item.business_id===id)}function conversation(id){return state.conversations.find(item=>item.conversation_id===id)}function renderInbox(){const groups=[['standard','STANDARD TRADEFLOW'],['custom','CUSTOM TRADEFLOW']];let html='';for(const [group,label] of groups){const bs=state.businesses.filter(item=>item.group===group);if(!bs.length)continue;html+=`<div class="group">${label}</div>`;for(const b of bs){html+=`<div class="business-label">${esc(b.name)} <small>• ${esc(b.phone_e164)}</small></div>`;for(const c of state.conversations.filter(item=>item.business_id===b.business_id)){html+=`<button class="conversation ${state.active===c.conversation_id?'active':''}" data-id="${esc(c.conversation_id)}"><div class="conversation-row"><b>${esc(c.customer_name)}</b><small>${esc(c.status)}</small></div><p>${esc(c.title)} — ${esc(c.latest_message)}</p></button>`}}}$('inbox-list').innerHTML=html;$('inbox-list').querySelectorAll('[data-id]').forEach(node=>node.onclick=()=>selectConversation(node.dataset.id))}function addBubble(role,text,meta=''){const empty=$('messages').querySelector('.empty');if(empty)empty.remove();const div=document.createElement('div');div.className=`bubble ${role}`;div.innerHTML=`${esc(text)}${meta?`<span class="meta">${esc(meta)}</span>`:''}`;$('messages').appendChild(div);$('messages').scrollTop=$('messages').scrollHeight}function renderHeader(){const c=conversation(state.active),b=c&&business(c.business_id);if(!c||!b)return;$('chat-name').textContent=`${c.customer_name} • ${b.name}`;$('chat-meta').textContent=`${b.channel_instance_id} → ${b.adapter_type} • ${c.customer_phone}`;$('chips').innerHTML=c.suggested_messages.map(text=>`<button class="chip" data-text="${esc(text)}">${esc(text)}</button>`).join('');$('chips').querySelectorAll('[data-text]').forEach(node=>node.onclick=()=>{$('message').value=node.dataset.text;$('message').focus()})}function renderContext(){const c=conversation(state.active),b=c&&business(c.business_id);if(!c||!b){$('inspect-content').innerHTML='<div class="empty">No conversation selected.</div>';return}$('inspect-content').innerHTML=`<div class="card"><h3>Resolved business channel</h3><div class="kv"><span>Business</span><b>${esc(b.name)}</b><span>Business ID</span><b>${esc(b.business_id)}</b><span>Channel</span><b>${esc(b.channel_instance_id)}</b><span>Number</span><b>${esc(b.phone_e164)}</b><span>Adapter</span><b>${esc(b.adapter_type)}</b><span>Customer</span><b>${esc(c.customer_name)} • ${esc(c.customer_phone)}</b><span>Scenario</span><b>${esc(c.scenario_group)}</b></div></div><div class="card"><h3>Ntheemba capabilities enabled</h3><div class="capabilities">${b.capabilities.map(cap=>`<span class="cap">${esc(cap)}</span>`).join('')}</div></div><div class="notice">TradeFlow may declare support only for these Ntheemba-known capabilities. Unknown capability names or methods are recorded for review and remain disabled.</div>`}function grouped(events){const map=new Map();for(const event of events){const old=map.get(event.span_id);if(!old||event.status!=='running')map.set(event.span_id,event)}return [...map.values()]}function renderPipeline(){const events=grouped(state.lastTrace);$('inspect-content').innerHTML=events.length?`<div class="card"><h3>Message pipeline</h3>${events.map(e=>`<div class="stage ${esc(e.status)}"><span class="dot"></span><span>${esc(e.node_id)}<br><em>${esc(e.component)}</em></span><em>${e.duration_ms==null?'—':Number(e.duration_ms).toFixed(2)+' ms'}</em></div>`).join('')}</div>`:'<div class="empty">Send a message to see business.resolve, capabilities.load, customer.resolve, interpretation, workflow and reply stages.</div>'}async function renderSession(){if(!state.active){$('inspect-content').innerHTML='<div class="empty">No conversation selected.</div>';return}const s=await api(`/dev/simulator/workspace/conversations/${encodeURIComponent(state.active)}`);if(!s.exists){$('inspect-content').innerHTML='<div class="empty">No active session yet.</div>';return}const fields=[['Conversation',s.conversation_id],['Business',s.business_id],['Customer ID',s.customer_id],['Flow',s.flow],['Stage',s.stage],['Mode',s.mode],['Revision',s.revision],['Product',s.selected_product||'—'],['Quantity',s.quantity??'—'],['Fulfilment',s.fulfilment_method||'—'],['Service',s.selected_service||'—'],['Date',s.selected_date||'—'],['Time',s.selected_time||'—'],['Client name',s.customer_name||'—'],['Submission',s.submitted_request_id||'—']];$('inspect-content').innerHTML=`<div class="card"><h3>Session inspector</h3><div class="kv">${fields.map(([k,v])=>`<span>${esc(k)}</span><b>${esc(v)}</b>`).join('')}</div></div><div class="card"><h3>Conversation history</h3>${s.history.map(t=>`<div class="history-row"><strong>${esc(t.role)}</strong><span>${esc(t.text)}</span></div>`).join('')||'<span class="muted">No history.</span>'}</div>`}async function renderInspect(){if(state.tab==='context')renderContext();else if(state.tab==='pipeline')renderPipeline();else await renderSession()}async function selectConversation(id){state.active=id;state.lastTrace=[];renderInbox();renderHeader();$('messages').innerHTML='<div class="empty">This simulated customer has an independent session. Use a quick message or type below.</div>';await renderInspect()}async function sendText(text){if(!state.active||!text.trim())return;const requestId=`REQ-SIM-${crypto.randomUUID()}`,messageId=`SIM-${crypto.randomUUID()}`;addBubble('customer',text,messageId.slice(0,18));const result=await api('/dev/simulator/workspace/messages',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({conversation_id:state.active,text,message_id:messageId,request_id:requestId})});for(const reply of result.replies)addBubble('assistant',reply.text||reply.caption||`[${reply.kind}]`,reply.message_id.slice(0,18));if(!result.replies.length)addBubble('system',`No reply published • ${result.status}`);state.lastTrace=await api(`/dev/simulator/requests/${encodeURIComponent(result.request_id)}/trace`);const c=conversation(state.active);if(c)c.latest_message=text;renderInbox();await renderInspect();return result}async function send(){const text=$('message').value.trim();if(!text)return;$('message').value='';try{await sendText(text)}catch(error){addBubble('system',`Request failed: ${error.message}`)}}async function runExample(){const c=conversation(state.active);if(!c)return;for(const text of c.suggested_messages){$('message').value=text;await sendText(text);await new Promise(resolve=>setTimeout(resolve,120))}}async function reset(){if(!state.active)return;await api(`/dev/simulator/workspace/conversations/${encodeURIComponent(state.active)}`,{method:'DELETE'});state.lastTrace=[];$('messages').innerHTML='<div class="empty">Conversation reset. Its next message starts a fresh session.</div>';await renderInspect()}document.querySelectorAll('.tab').forEach(tab=>tab.onclick=async()=>{document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));tab.classList.add('active');state.tab=tab.dataset.tab;await renderInspect()});$('send').onclick=send;$('message').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}};$('run-example').onclick=()=>runExample().catch(e=>addBubble('system',e.message));$('reset').onclick=()=>reset().catch(e=>addBubble('system',e.message));async function init(){state.businesses=await api('/dev/simulator/workspace/businesses');state.conversations=await api('/dev/simulator/workspace/conversations');$('business-count').textContent=`${state.businesses.length} businesses`;$('conversation-count').textContent=`${state.conversations.length} conversations`;renderInbox();if(state.conversations.length)await selectConversation(state.conversations[0].conversation_id)}init().catch(error=>{$('inbox-list').innerHTML=`<div class="notice">${esc(error.message)}</div>`});
</script>
</body>
</html>"""


@router.get("/workspace", response_class=HTMLResponse, include_in_schema=False)
async def multi_conversation_workspace() -> HTMLResponse:
    """Render the Phase 11.14 multi-business conversation workspace."""

    nonce = token_urlsafe(18)
    html = _WORKSPACE_HTML.replace("__CSP_NONCE__", nonce)
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                f"default-src 'none'; style-src 'nonce-{nonce}'; "
                f"script-src 'nonce-{nonce}'; connect-src 'self'; "
                "img-src 'self' data: https:; base-uri 'none'; form-action 'none'; "
                "frame-ancestors 'none'"
            ),
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
    )
