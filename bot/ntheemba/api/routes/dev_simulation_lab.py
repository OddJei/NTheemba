"""Developer-only, transport-v2 simulation laboratory.

The lab is deliberately not a gateway.  It is a protected local harness that
uses the same v2 ingress and outbound queue contracts as an independently
deployed adapter, while keeping gateway credentials on the server.
"""

# ruff: noqa: E501, RUF001

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from ntheemba.api.routes.dev_pipeline import pipeline_request_status
from ntheemba.api.routes.transport import (
    TransportInboundRequest,
    enqueue_transport_inbound,
)

router = APIRouter(
    prefix="/dev/simulation-lab",
    tags=["developer-simulation-lab"],
    include_in_schema=False,
)


class LabScenarioRequest(BaseModel):
    """The only caller-controlled values are neutral transport envelope fields."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    mode: Literal["deterministic", "local_end_to_end"] = "deterministic"
    gateway_id: str = Field(alias="gatewayId", min_length=1, max_length=100)
    external_session_id: str = Field(alias="externalSessionId", min_length=1, max_length=200)
    recipient_identifier: str = Field(alias="recipientIdentifier", min_length=8, max_length=200)
    sender_identifier: str = Field(alias="senderIdentifier", min_length=8, max_length=200)
    text: str = Field(min_length=1, max_length=4_000)
    metadata: dict[str, str] = Field(default_factory=dict)
    fault: Literal["none", "invalid_credential", "expired_timestamp", "unknown_binding"] = "none"


class LabScenarioResponse(BaseModel):
    correlation_id: str = Field(alias="correlationId")
    status: str
    detail: str = ""
    mode: str
    evidence: dict[str, object]


def _server_gateway_token(request: Request, gateway_id: str) -> str:
    settings = request.app.state.settings
    normalized = gateway_id.casefold()
    if normalized not in settings.transport_simulator_gateways:
        raise HTTPException(status_code=403, detail="Gateway is not approved for simulation.")
    token = settings.transport_gateway_tokens.get(normalized)
    if token is None:
        raise HTTPException(status_code=404, detail="No local development gateway is configured.")
    return token


def _end_to_end_available(request: Request) -> bool:
    snapshot = request.app.state.storage_runtime
    settings = request.app.state.settings
    return bool(
        settings.tradeflow_onboarding_tokens_json
        and getattr(snapshot, "redis_runtime", None) is not None
        and getattr(snapshot, "postgres_runtime", None) is not None
    )


def _masked(value: object) -> str:
    """Keep correlation evidence useful without returning customer identifiers."""

    text = str(value or "")
    return "" if not text else f"…{text[-4:]}"


def _safe_queue_records(records: tuple[dict[str, object], ...]) -> list[dict[str, object]]:
    return [
        {
            "deliveryId": record.get("delivery_id", ""),
            "messageId": record.get("message_id", ""),
            "attempt": record.get("attempt", 0),
            "reason": record.get("reason", ""),
            "sender": _masked(record.get("customer_phone")),
            "recipient": _masked(record.get("recipient_phone")),
            "textLength": len(str(record.get("text") or "")),
        }
        for record in records
    ]


def _safe_lab_evidence(status: object) -> dict[str, object]:
    """Allowlist lab evidence rather than exposing the general pipeline payload."""

    return {
        "inbound": _safe_queue_records(status.inbound),
        "outbound": _safe_queue_records(status.outbound),
        "inboundDeadLetters": _safe_queue_records(status.inbound_dead_letters),
        "outboundDeadLetters": _safe_queue_records(status.outbound_dead_letters),
        "audit": [
            {
                "eventType": event.get("event_type", ""),
                "severity": event.get("severity", ""),
                "occurredAt": event.get("occurred_at", ""),
            }
            for event in status.audit_events
        ],
        "warnings": list(status.warnings),
    }


@router.get("/readiness")
async def lab_readiness(request: Request) -> dict[str, object]:
    """Expose safe readiness facts, never gateway tokens or business authority."""

    runtime = request.app.state.storage_runtime
    snapshot = await runtime.snapshot()
    return {
        "deterministic": {"available": True, "proof": "controlled local workflow dependencies"},
        "localEndToEnd": {
            "available": _end_to_end_available(request),
            "proof": "requires local Redis, PostgreSQL, and verified test TradeFlow integration",
        },
        "gatewayIds": [
            gateway_id
            for gateway_id in request.app.state.settings.transport_simulator_gateways
            if gateway_id in request.app.state.settings.transport_gateway_tokens
        ],
        "storage": {
            "queue": snapshot.gateway_queue_backend,
            "businessRegistry": snapshot.business_backend,
            "sessions": snapshot.session_backend,
        },
        "warning": "Local evidence is not real-gateway or deployed-integration proof.",
    }


@router.post("/scenarios", response_model=LabScenarioResponse)
async def run_lab_scenario(payload: LabScenarioRequest, request: Request) -> LabScenarioResponse:
    """Submit one neutral envelope through the production v2 ingress function."""

    if payload.mode == "local_end_to_end" and not _end_to_end_available(request):
        raise HTTPException(
            status_code=409, detail="Local end-to-end mode is not verified or ready."
        )
    correlation_id = f"LAB-{uuid4()}"
    occurred_at = datetime.now(UTC)
    recipient = payload.recipient_identifier
    authorization = f"Bearer {_server_gateway_token(request, payload.gateway_id)}"
    if payload.fault == "invalid_credential":
        authorization = "Bearer invalid-lab-credential"
    elif payload.fault == "expired_timestamp":
        occurred_at -= timedelta(
            seconds=request.app.state.settings.transport_replay_window_seconds + 1
        )
    elif payload.fault == "unknown_binding":
        recipient = f"unknown:{uuid4()}"
    envelope = TransportInboundRequest(
        messageId=f"LAB-MSG-{uuid4()}",
        externalSessionId=payload.external_session_id,
        recipientIdentifier=recipient,
        senderIdentifier=payload.sender_identifier,
        text=payload.text,
        occurredAt=occurred_at,
        correlationId=correlation_id,
        metadata={**payload.metadata, "source": "dev.simulation_lab", "mode": payload.mode},
    )
    try:
        accepted = await enqueue_transport_inbound(
            envelope,
            request,
            authorization=authorization,
            gateway_id_header=payload.gateway_id,
        )
    except HTTPException as error:
        return LabScenarioResponse(
            correlationId=correlation_id,
            status="rejected",
            detail=str(error.detail),
            mode=payload.mode,
            evidence={"stage": "transport.ingress", "fault": payload.fault},
        )
    status = await pipeline_request_status(correlation_id, request)
    safe_evidence = _safe_lab_evidence(status)
    return LabScenarioResponse(
        correlationId=correlation_id,
        status="accepted",
        mode=payload.mode,
        evidence={
            "stage": "transport.ingress",
            "deliveryId": accepted.delivery_id,
            "duplicate": accepted.duplicate,
            **safe_evidence,
        },
    )


@router.get("/evidence/{correlation_id}")
async def lab_evidence(correlation_id: str, request: Request) -> dict[str, object]:
    """Return redacted correlation-scoped queue and audit evidence."""

    status = await pipeline_request_status(correlation_id, request)
    return {"correlationId": correlation_id, **_safe_lab_evidence(status)}


_LAB_HTML = """<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Ntheemba Simulation Lab</title><style nonce=\"__CSP_NONCE__\">:root{font-family:system-ui,sans-serif;color-scheme:dark}body{margin:0;background:#07111f;color:#edf4ff}.shell{max-width:1120px;margin:auto;padding:20px}.top{display:flex;gap:14px;align-items:center;flex-wrap:wrap}.top h1{margin:0;font-size:22px}.muted{color:#aab9ce}.notice,.card{border:1px solid #34506e;border-radius:12px;padding:14px;background:#0c1a2d}.notice{margin:15px 0;color:#f4d88c}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.wide{grid-column:1/-1}.field{display:grid;gap:5px;margin:10px 0}.field label{font-size:12px;color:#b8c9df}input,textarea,select,button{font:inherit;border-radius:8px;border:1px solid #3e5877;background:#07111f;color:inherit;padding:9px}textarea{min-height:88px}button{background:#3dca91;color:#04140e;font-weight:700;cursor:pointer}.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}.tab{background:#16324f;color:#edf4ff}.tab.active{background:#3dca91;color:#04140e}pre{white-space:pre-wrap;word-break:break-word;max-height:460px;overflow:auto;background:#06101d;padding:12px;border-radius:8px}@media(max-width:680px){.grid{grid-template-columns:1fr}.wide{grid-column:auto}.shell{padding:13px}}</style></head><body><main class=\"shell\"><header class=\"top\"><h1>Ntheemba Simulation Lab</h1><span class=\"muted\">Developer-only production-path testing</span><a class=\"muted\" href=\"/dev/simulator/workspace\">Legacy logic simulator</a><a class=\"muted\" href=\"/dev/pipeline\">Legacy queue console</a></header><p class=\"notice\">This lab sends a transport-neutral envelope through Ntheemba’s v2 ingress. Ntheemba, not this page, resolves the business, shop scope, capability, and channel authority. Local results do not prove a real gateway or deployed TradeFlow integration.</p><nav class=\"tabs\" aria-label=\"Simulation lab views\"><button class=\"tab active\" data-tab=\"scenario\">1. Scenario</button><button class=\"tab\" data-tab=\"nodes\">2. Node path</button><button class=\"tab\" data-tab=\"delivery\">3. Delivery evidence</button></nav><section id=\"scenario\" class=\"view\"><div class=\"grid\"><div class=\"card\"><h2>Neutral inbound envelope</h2><div class=\"field\"><label>Mode</label><select id=\"mode\"><option value=\"deterministic\">Deterministic simulation</option><option value=\"local_end_to_end\">Local end-to-end (when ready)</option></select></div><div class=\"field\"><label>Gateway</label><select id=\"gateway\"></select></div><div class=\"field\"><label>External session</label><input id=\"session\" value=\"sim-wa-serahs\"></div><div class=\"field\"><label>Recipient identity</label><input id=\"recipient\" value=\"+260976078440\"></div><div class=\"field\"><label>Sender identity</label><input id=\"sender\" value=\"+260971234567\"></div><div class=\"field\"><label>Text</label><textarea id=\"text\">I want braids</textarea></div><div class=\"field\"><label>Safe fault</label><select id=\"fault\"><option value=\"none\">None</option><option value=\"invalid_credential\">Invalid gateway credential</option><option value=\"expired_timestamp\">Expired timestamp</option><option value=\"unknown_binding\">Unknown channel binding</option></select></div><button id=\"run\">Run scenario</button><p id=\"status\" class=\"muted\" aria-live=\"polite\"></p></div><div class=\"card\"><h2>Readiness</h2><pre id=\"readiness\">Loading…</pre></div></div></section><section id=\"nodes\" class=\"view\" hidden><div class=\"card wide\"><h2>Observed node path</h2><p class=\"muted\">Each item is redacted evidence from the real ingress and queue. Worker, NCPC, TradeFlow, and reply nodes appear once local end-to-end processing has completed.</p><pre id=\"nodes-data\">Run a scenario first.</pre></div></section><section id=\"delivery\" class=\"view\" hidden><div class=\"card wide\"><h2>Outbound delivery evidence</h2><p class=\"muted\">Claim and acknowledgement are available only after the worker publishes an outbound delivery. A failed acknowledgement terminally dead-letters the claimed delivery.</p><pre id=\"delivery-data\">Run a scenario and wait for a worker-produced outbound delivery.</pre></div></section></main><script nonce=\"__CSP_NONCE__\">const $=id=>document.getElementById(id);let last=null;const esc=v=>JSON.stringify(v,null,2);async function api(url,opts){const r=await fetch(url,opts);const data=r.status===204?null:await r.json();if(!r.ok)throw new Error(data.detail||r.statusText);return data}function tabs(){document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('.view').forEach(x=>x.hidden=x.id!==b.dataset.tab)})}async function load(){const r=await api('/dev/simulation-lab/readiness');$('readiness').textContent=esc(r);$('gateway').innerHTML=(r.gatewayIds||[]).map(x=>`<option>${x}</option>`).join('');if(!r.gatewayIds.length)$('status').textContent='No local development gateway is configured.'}async function run(){try{$('status').textContent='Submitting through transport v2…';last=await api('/dev/simulation-lab/scenarios',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({mode:$('mode').value,gatewayId:$('gateway').value,externalSessionId:$('session').value,recipientIdentifier:$('recipient').value,senderIdentifier:$('sender').value,text:$('text').value,fault:$('fault').value})});$('nodes-data').textContent=esc(last);$('delivery-data').textContent=esc(last.evidence?.outbound||'No outbound delivery observed yet.');$('status').textContent=`${last.status}: ${last.detail||last.correlationId}`}catch(e){$('status').textContent=e.message}}tabs();$('run').onclick=run;load().catch(e=>$('status').textContent=e.message)</script></body></html>"""


@router.get("", response_class=HTMLResponse)
async def simulation_lab_console() -> HTMLResponse:
    nonce = token_urlsafe(18)
    return HTMLResponse(
        _LAB_HTML.replace("__CSP_NONCE__", nonce).replace(
            "Claim and acknowledgement are available only after the worker publishes an outbound delivery. A failed acknowledgement terminally dead-letters the claimed delivery.",
            "Delivery state is shown after the worker publishes an outbound delivery. Gateway claim and acknowledgement remain owned by the gateway transport boundary.",
        ),
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                f"default-src 'none'; style-src 'nonce-{nonce}'; script-src 'nonce-{nonce}'; "
                "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"
            ),
        },
    )
