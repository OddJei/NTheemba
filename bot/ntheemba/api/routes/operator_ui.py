"""Plain-language, server-rendered operator workspace for Ntheemba."""

# ruff: noqa: E501

from __future__ import annotations

import hmac
from dataclasses import dataclass, replace
from html import escape
from secrets import token_urlsafe
from time import monotonic
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ntheemba.application.operator_control_plane import OperatorControlPlaneError
from ntheemba.domain.business import BusinessProfile

router = APIRouter(prefix="/operator", tags=["operator-ui"], include_in_schema=False)
_COOKIE = "ntheemba_operator_session"
_TTL_SECONDS = 3_600

_SERVICE_COPY = {
    "business.information": (
        "Business information",
        "Help customers with approved business details.",
    ),
    "business.hours": ("Opening hours", "Let customers ask when the business is open."),
    "faq.search": ("Frequently asked questions", "Help customers find approved answers."),
    "client.identify": (
        "Find existing customers",
        "Find a customer when they choose to identify themselves.",
    ),
    "client.create": ("Create customer profiles", "Create a customer profile after confirmation."),
    "product.catalogue": (
        "Product search",
        "Let customers ask about products available from this business.",
    ),
    "product.order": ("Orders", "Let customers request an order from this business."),
    "fulfilment.delivery": ("Delivery", "Support delivery options for customer orders."),
    "fulfilment.collection": ("Collection", "Support collection options for customer orders."),
    "service.catalogue": ("Services", "Let customers browse the business services."),
    "appointment.create": ("Book appointments", "Let customers book an appointment."),
    "appointment.reschedule": ("Reschedule appointments", "Let customers change an appointment."),
    "appointment.cancel": ("Cancel appointments", "Let customers cancel an appointment."),
    "loyalty.read": ("Loyalty information", "Let customers view their loyalty information."),
    "handover.create": (
        "Speak to staff / Human support",
        "Let customers ask for help from business staff.",
    ),
}


@dataclass(frozen=True, slots=True)
class OperatorSession:
    actor: str
    csrf: str
    expires_at: float


@dataclass(frozen=True, slots=True)
class PendingOperatorAction:
    """A short-lived, session-bound description of one confirmed UI change."""

    actor: str
    csrf: str
    business_id: str
    kind: str
    resource_id: str
    enabled: bool
    expires_at: float


def _sessions(request: Request) -> dict[str, OperatorSession]:
    return request.app.state.operator_ui_sessions


def _pending_actions(request: Request) -> dict[str, PendingOperatorAction]:
    return request.app.state.operator_ui_actions


def _issue_action(
    request: Request,
    session: OperatorSession,
    *,
    business_id: str,
    kind: str,
    resource_id: str,
    enabled: bool,
) -> str:
    token = token_urlsafe(24)
    _pending_actions(request)[token] = PendingOperatorAction(
        actor=session.actor,
        csrf=session.csrf,
        business_id=business_id,
        kind=kind,
        resource_id=resource_id,
        enabled=enabled,
        expires_at=monotonic() + 600,
    )
    return token


def _consume_action(
    request: Request, session: OperatorSession, token: str
) -> PendingOperatorAction:
    action = _pending_actions(request).pop(token, None)
    if (
        action is None
        or action.expires_at <= monotonic()
        or action.actor != session.actor
        or not hmac.compare_digest(action.csrf, session.csrf)
    ):
        raise HTTPException(400, "This confirmation has expired. Please start again.")
    return action


def _pending_action(
    request: Request, session: OperatorSession, token: str
) -> PendingOperatorAction:
    action = _pending_actions(request).get(token)
    if (
        action is None
        or action.expires_at <= monotonic()
        or action.actor != session.actor
        or not hmac.compare_digest(action.csrf, session.csrf)
    ):
        raise HTTPException(400, "This confirmation has expired. Please start again.")
    return action


def _session(request: Request) -> OperatorSession | None:
    token = request.cookies.get(_COOKIE, "")
    session = _sessions(request).get(token)
    if session is None or session.expires_at <= monotonic():
        _sessions(request).pop(token, None)
        return None
    return session


def _require_session(request: Request) -> OperatorSession:
    session = _session(request)
    if session is None:
        raise HTTPException(status_code=401, detail="Please sign in to use the operator workspace.")
    return session


def _form(request: Request, session: OperatorSession, body: bytes) -> dict[str, str]:
    values = {key: items[-1] for key, items in parse_qs(body.decode("utf-8", "replace")).items()}
    if not hmac.compare_digest(values.get("csrf", ""), session.csrf):
        raise HTTPException(
            status_code=403, detail="Your session has expired. Please sign in again."
        )
    return values


def _page(
    title: str, content: str, *, session: OperatorSession | None = None, dev: bool = False
) -> HTMLResponse:
    nav = (
        ""
        if session is None
        else (
            '<nav aria-label="Operator navigation"><a href="/operator">Overview</a><a href="/operator/businesses">Businesses</a>'
            '<a href="/operator/status">System Status</a>'
            + ('<a class="advanced" href="/dev/console">Developer Tools</a>' if dev else "")
            + '<form method="post" action="/operator/logout"><input type="hidden" name="csrf" value="'
            + escape(session.csrf)
            + '"><button>Sign out</button></form></nav>'
        )
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} | Ntheemba</title>
  <style>
    :root{{font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;color:#172033;background:#f4f7fb;--ink:#172033;--muted:#667085;--navy:#102a56;--violet:#6d42e7;--violet-dark:#5430c3;--mint:#00a78e;--line:#e4e9f2;--surface:#ffffff;--ok:#087d63;--warn:#b54708}}
    *{{box-sizing:border-box}} body{{margin:0;min-height:100vh;background:radial-gradient(circle at 8% -10%,#dfe7ff 0,transparent 28rem),#f4f7fb;line-height:1.5}}
    .app-header{{position:sticky;top:0;z-index:10;display:flex;align-items:center;justify-content:space-between;gap:1rem;min-height:76px;padding:12px max(24px,calc((100% - 1180px)/2));color:#fff;background:linear-gradient(112deg,#102a56 0%,#193d78 52%,#253f8e 100%);box-shadow:0 8px 24px #102a562e}}
    .brand{{display:flex;align-items:center;gap:11px;color:#fff;text-decoration:none;letter-spacing:-.01em}} .brand-mark{{display:grid;place-items:center;width:38px;height:38px;border:1px solid #ffffff42;border-radius:12px;background:linear-gradient(145deg,#8b6cff,#4b2fbc);font-weight:800;font-size:1.1rem;box-shadow:0 6px 16px #12066b55}} .brand-copy{{display:grid;line-height:1.05}} .brand-copy b{{font-size:1rem}} .brand-copy small{{margin-top:4px;color:#cfdaff;font-size:.72rem;font-weight:600;letter-spacing:.04em;text-transform:uppercase}}
    .header-actions nav{{display:flex;align-items:center;gap:4px;flex-wrap:wrap}} .header-actions nav a{{padding:9px 10px;border-radius:9px;color:#e7edff;text-decoration:none;font-size:.9rem;font-weight:650}} .header-actions nav a:hover{{background:#ffffff18;color:#fff}} .header-actions nav .advanced{{color:#ffe7a3}} .header-actions nav form{{margin:0}} .header-actions nav button{{padding:8px 12px;border:1px solid #ffffff3d;border-radius:9px;background:#ffffff12;box-shadow:none}}
    main{{width:min(1180px,calc(100% - 48px));margin:0 auto;padding:42px 0 58px}} h1,h2,h3{{color:var(--ink);letter-spacing:-.035em}} h1{{margin:0 0 8px;font-size:clamp(1.8rem,4vw,2.65rem);line-height:1.08}} h2{{margin:0;font-size:1.12rem}} h3{{margin:.3rem 0 .65rem;font-size:1rem}} p{{color:var(--muted)}} a{{color:var(--violet)}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:16px;margin-top:22px}} .card,details,form.panel{{border:1px solid var(--line);border-radius:16px;background:var(--surface);box-shadow:0 12px 28px #1a27430d}} .card{{padding:20px;transition:transform .18s ease,box-shadow .18s ease}} .card:hover{{transform:translateY(-2px);box-shadow:0 16px 30px #1a274316}} .card b{{display:block;color:#667085;font-size:.78rem;letter-spacing:.07em;text-transform:uppercase}} .card h2{{margin-top:10px;font-size:1.8rem}}
    .status{{font-weight:750}} .ok{{color:var(--ok)}} .attention{{color:var(--warn)}} .notice{{margin:18px 0;padding:14px 16px;border:1px solid #fed7aa;border-radius:12px;border-left:4px solid #f79009;background:#fffaeb;color:#7a2e0e}} .muted{{color:var(--muted)}}
    button,.button{{display:inline-flex;align-items:center;justify-content:center;min-height:42px;padding:10px 15px;border:0;border-radius:10px;background:linear-gradient(135deg,var(--violet),var(--violet-dark));color:#fff;font:inherit;font-weight:700;cursor:pointer;box-shadow:0 8px 16px #6239d12b;text-decoration:none;transition:transform .16s ease,box-shadow .16s ease}} button:hover,.button:hover{{transform:translateY(-1px);box-shadow:0 11px 20px #6239d13d}} button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,summary:focus-visible{{outline:3px solid #f9bc43;outline-offset:3px}}
    label{{display:grid;gap:7px;margin:16px 0;font-size:.88rem;font-weight:700;color:#344054}} input,select,textarea{{width:100%;padding:11px 12px;border:1px solid #cdd5df;border-radius:10px;background:#fff;color:var(--ink);font:inherit;transition:border-color .16s ease,box-shadow .16s ease}} input:focus,select:focus,textarea:focus{{border-color:#8a6cf0;box-shadow:0 0 0 4px #6d42e71a;outline:0}} .row{{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;padding:16px 0;border-top:1px solid var(--line)}} details{{margin:18px 0;padding:14px 16px}} summary{{cursor:pointer;font-weight:750;color:#344054}} .inline-help{{display:inline-block;margin:0;padding:0;border:0;box-shadow:none;background:transparent;vertical-align:middle}} .inline-help summary{{display:grid;place-items:center;width:22px;height:22px;border-radius:50%;background:#ede9fe;color:var(--violet)}} .inline-help p{{max-width:22rem;margin:.7rem 0 0}} .advanced-setup summary{{font-weight:750}}
    .auth-layout{{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(330px,.95fr);gap:28px;align-items:stretch;max-width:980px;margin:clamp(12px,5vh,56px) auto}} .auth-intro{{padding:38px;border-radius:22px;background:linear-gradient(145deg,#102a56,#273d8d);color:#fff;box-shadow:0 20px 44px #112a5633}} .auth-intro h1{{color:#fff;font-size:clamp(2.1rem,5vw,3.3rem)}} .auth-intro p{{max-width:34rem;color:#d9e4ff;font-size:1.02rem}} .auth-intro ul{{display:grid;gap:12px;padding:0;margin:28px 0 0;list-style:none;color:#edf2ff}} .auth-intro li{{display:flex;gap:10px;align-items:center}} .auth-intro li::before{{content:"✓";display:grid;place-items:center;width:22px;height:22px;border-radius:50%;background:#00a78e;color:#fff;font-weight:900;font-size:.75rem}} form.panel{{align-self:center;padding:30px}} .login-kicker{{margin:0;color:var(--violet);font-size:.75rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase}} .login-card h2{{margin:8px 0 4px;font-size:1.6rem}} .login-card p{{margin:0 0 22px}} .login-card button{{width:100%;margin-top:7px}}
    @media(max-width:760px){{.app-header{{position:relative;padding:13px 20px}}.header-actions{{width:100%}}.header-actions nav{{justify-content:flex-start}}main{{width:min(100% - 32px,1180px);padding:26px 0 42px}}.auth-layout{{grid-template-columns:1fr;gap:16px;margin:0 auto}}.auth-intro,form.panel{{padding:24px}}.auth-intro ul{{margin-top:20px}}}} @media(max-width:420px){{.brand-copy small{{display:none}}.header-actions nav a{{padding:7px 6px;font-size:.82rem}}.grid{{grid-template-columns:1fr}}}}
  </style>
</head>
<body>
  <header class="app-header"><a class="brand" href="{"/operator" if session is not None else "/operator/login"}" aria-label="Ntheemba operator workspace"><span class="brand-mark">N</span><span class="brand-copy"><b>Ntheemba</b><small>Operator workspace</small></span></a><div class="header-actions">{nav}</div></header>
  <main>{content}</main>
</body>
</html>"""
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'self'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
        },
    )


async def _data(
    request: Request,
) -> tuple[tuple[BusinessProfile, ...], dict[str, tuple[object, ...]], tuple[object, ...]]:
    registry = request.app.state.storage_runtime.business_registry
    businesses = await registry.list_businesses()
    channels = await registry.list_channels()
    integrations = {
        item.business_id: await registry.list_integrations(item.business_id) for item in businesses
    }
    return businesses, integrations, channels


def _help(text: str) -> str:
    return f"<details><summary>Help</summary><p>{escape(text)}</p></details>"


def _inline_help(label: str, text: str) -> str:
    return (
        '<details class="inline-help"><summary aria-label="What does '
        + escape(label)
        + ' mean?">?</summary><p>'
        + escape(text)
        + "</p></details>"
    )


def _action_form(session: OperatorSession, token: str, label: str) -> str:
    return (
        '<form method="post" action="/operator/confirm"><input type="hidden" name="csrf" value="'
        + escape(session.csrf)
        + '"><input type="hidden" name="action_token" value="'
        + escape(token)
        + '"><button>'
        + escape(label)
        + "</button></form>"
    )


@router.get("/login")
async def login() -> HTMLResponse:
    return _page(
        "Sign in",
        '<section class="auth-layout"><div class="auth-intro"><p class="login-kicker">Ntheemba operations</p><h1>Run every business with confidence.</h1><p>Your dedicated workspace for businesses, services, channels, and connections. Developer tools remain separate.</p><ul><li>Clear status at a glance</li><li>Tenant-aware operations</li><li>Confirmed, audited changes</li></ul></div><form class="panel login-card" method="post" action="/operator/session"><p class="login-kicker">Secure access</p><h2>Welcome back</h2><p>Enter your operator details to continue.</p><label>Operator name<input name="actor" autocomplete="username" required></label><label>Operator access token<input name="token" type="password" autocomplete="current-password" required></label><button>Sign in to workspace</button></form></section>',
    )


@router.post("/session")
async def create_session(request: Request) -> RedirectResponse:
    form = {
        key: items[-1]
        for key, items in parse_qs((await request.body()).decode("utf-8", "replace")).items()
    }
    settings = request.app.state.settings
    supplied, actor = form.get("token", "").strip(), form.get("actor", "").strip()
    configured = settings.operator_api_token
    allowed = {item for item in settings.operator_api_allowed_actors.split(",") if item}
    if (
        not actor
        or configured is None
        or not hmac.compare_digest(supplied, configured.get_secret_value())
        or (allowed and actor not in allowed)
    ):
        return RedirectResponse("/operator/login", status_code=303)
    token, csrf = token_urlsafe(32), token_urlsafe(24)
    _sessions(request)[token] = OperatorSession(actor, csrf, monotonic() + _TTL_SECONDS)
    response = RedirectResponse("/operator", status_code=303)
    response.set_cookie(
        _COOKIE,
        token,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        max_age=_TTL_SECONDS,
        path="/operator",
    )
    return response


@router.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    session = _require_session(request)
    _form(request, session, await request.body())
    _sessions(request).pop(request.cookies.get(_COOKIE, ""), None)
    response = RedirectResponse("/operator/login", status_code=303)
    response.delete_cookie(_COOKIE, path="/operator")
    return response


@router.get("")
async def overview(request: Request) -> HTMLResponse:
    session = _require_session(request)
    businesses, integrations, channels = await _data(request)
    active = sum(item.enabled for item in businesses)
    attention = sum(not item.enabled for item in businesses)
    configured = sum(
        any(item.enabled and item.status == "active" for item in values)
        for values in integrations.values()
    )
    channel_ok = sum(getattr(item, "enabled", False) for item in channels)
    message = (
        "Everything is working normally."
        if not attention
        else f"{attention} businesses need attention."
    )
    return _page(
        "Overview",
        f'<h1>Overview <a class="help" href="#help">Help</a></h1><p class="status {"ok" if not attention else "attention"}">{message}</p><section class="grid"><article class="card"><b>Registered businesses</b><h2>{len(businesses)}</h2></article><article class="card"><b>Active businesses</b><h2>{active}</h2></article><article class="card"><b>WhatsApp channels</b><h2>{channel_ok} active</h2></article><article class="card"><b>TradeFlow connections</b><h2>{configured} configured</h2></article></section><p><a class="button" href="/operator/businesses">Manage businesses</a></p><div id="help">{_help("Use this page to see what needs attention, then open Businesses to manage a business. Connection counts reflect saved configuration, not a live external check.")}</div>',
        session=session,
        dev=request.app.state.settings.developer_tools_active,
    )


@router.get("/businesses")
async def businesses(request: Request) -> HTMLResponse:
    session = _require_session(request)
    profiles, integrations, channels = await _data(request)
    cards = []
    for item in profiles:
        channel = next(
            (
                entry
                for entry in channels
                if getattr(entry, "business_id", None) == item.business_id
            ),
            None,
        )
        connection = any(
            entry.enabled and entry.status == "active" for entry in integrations[item.business_id]
        )
        cards.append(
            f'<article class="card"><h2>{escape(item.display_name)}</h2><p>{escape(item.business_type or "Business")}</p><p class="status {"ok" if item.enabled else "attention"}">{"Active" if item.enabled else "Paused"}</p><p>{len(item.declared_capabilities)} enabled services · WhatsApp: {"Connected" if channel and channel.enabled else "Not connected"} · TradeFlow: {"Configured" if connection else "Not configured"}</p><a class="button" href="/operator/businesses/{escape(item.business_id)}">Manage Business</a></article>'
        )
    empty = '<p class="notice">No businesses are registered yet.</p>' if not cards else ""
    return _page(
        "Businesses",
        '<h1>Businesses <a class="help" href="#help">Help</a></h1><p><a class="button" href="/operator/businesses/add">Add Business</a></p><section class="grid">'
        + "".join(cards)
        + "</section>"
        + empty
        + f'<div id="help">{_help("Open a business to manage its services, WhatsApp channel, and connections. Internal identifiers are kept in Technical details.")}</div>',
        session=session,
        dev=request.app.state.settings.developer_tools_active,
    )


@router.get("/businesses/add")
async def add_business(request: Request) -> HTMLResponse:
    session = _require_session(request)
    options = "".join(
        f'<label><input type="checkbox" name="service" value="{key}"> {label}</label>'
        for key, (label, _) in _SERVICE_COPY.items()
    )
    return _page(
        "Add Business",
        f'<h1>Add Business</h1>{_help("Add the business details and choose the services it should offer. You can connect WhatsApp and TradeFlow from the business page after it is created.")}<form class="panel" method="post" action="/operator/businesses"><input type="hidden" name="csrf" value="{escape(session.csrf)}"><label>Business name<input name="name" required></label><label>Business type<input name="type" placeholder="For example, retail or salon"></label><label>Description (optional)<textarea name="description"></textarea></label><fieldset><legend>Business Services</legend>{options}</fieldset><button>Add Business</button></form>',
        session=session,
        dev=request.app.state.settings.developer_tools_active,
    )


@router.post("/businesses")
async def register_business(request: Request) -> RedirectResponse:
    session = _require_session(request)
    body = await request.body()
    form = _form(request, session, body)
    services = parse_qs(body.decode("utf-8", "replace")).get("service", ["business.information"])
    capabilities = frozenset(item for item in services if item in _SERVICE_COPY) or frozenset(
        {"business.information"}
    )
    name = form.get("name", "").strip()
    business_id = "business-" + "-".join(
        "".join(ch for ch in part.lower() if ch.isalnum()) for part in name.split()
    )
    if not name or business_id == "business-":
        raise HTTPException(400, "A business name is required.")
    try:
        await request.app.state.operator_control_plane.register_business(
            BusinessProfile(
                business_id,
                name,
                "operator_managed",
                capabilities,
                business_type=form.get("type", "").strip(),
                description=form.get("description", "").strip(),
                runtime_revision=1,
            ),
            actor_id=session.actor,
            request_id=f"operator-ui-{token_urlsafe(12)}",
        )
    except (OperatorControlPlaneError, ValueError) as error:
        raise HTTPException(
            400, "This business could not be added. Check the details and try again."
        ) from error
    return RedirectResponse(f"/operator/businesses/{business_id}", status_code=303)


@router.get("/businesses/{business_id}")
async def detail(business_id: str, request: Request) -> HTMLResponse:
    session = _require_session(request)
    profiles, integrations, channels = await _data(request)
    item = next((entry for entry in profiles if entry.business_id == business_id), None)
    if item is None:
        raise HTTPException(404, "This business could not be found.")
    channel = next(
        (entry for entry in channels if getattr(entry, "business_id", None) == business_id), None
    )
    connection = any(
        entry.enabled and entry.status == "active" for entry in integrations[business_id]
    )
    action_label = "Pause" if item.enabled else "Resume"
    action = _issue_action(
        request,
        session,
        business_id=business_id,
        kind="business",
        resource_id=business_id,
        enabled=not item.enabled,
    )
    return _page(
        item.display_name,
        f'<h1>{escape(item.display_name)} <a class="help" href="#help">Help</a></h1><p class="status {"ok" if item.enabled else "attention"}">{"Active" if item.enabled else "Paused"}</p><section class="grid"><article class="card"><h2>Business Services</h2><p>{len(item.declared_capabilities)} enabled</p><a href="/operator/businesses/{escape(business_id)}/services">Manage Services</a></article><article class="card"><h2>WhatsApp</h2><p>{"Connected" if channel and channel.enabled else "Not connected"}</p><a href="/operator/businesses/{escape(business_id)}/channels">Manage WhatsApp</a></article><article class="card"><h2>Connections</h2><p>{"Configured" if connection else "Not configured"}</p><a href="/operator/businesses/{escape(business_id)}/connections">Manage Connections</a></article></section><section class="panel"><p class="notice">! {action_label} changes whether Ntheemba can serve this business. You will be asked to confirm.</p>{_action_form(session, action, action_label + " business")}</section><details><summary>Technical details</summary><p>Business ID: {escape(item.business_id)}<br>Configuration type: {escape(item.adapter_type)}<br>Service IDs: {escape(", ".join(sorted(item.declared_capabilities)))}</p></details><div id="help">{_help("Manage services to choose what customers can do. WhatsApp and connection status are configuration status, and technical details are shown only when needed.")}</div>',
        session=session,
        dev=request.app.state.settings.developer_tools_active,
    )


@router.get("/businesses/{business_id}/services")
async def services(business_id: str, request: Request) -> HTMLResponse:
    session = _require_session(request)
    business = await request.app.state.storage_runtime.business_registry.get_business(business_id)
    if business is None:
        raise HTTPException(404, "This business could not be found.")
    rows = "".join(
        f'<div class="row"><div><strong>{label} {_inline_help(label, description)}</strong><p class="muted">{escape(description)}</p></div>{_action_form(session, _issue_action(request, session, business_id=business_id, kind="service", resource_id=key, enabled=key not in business.declared_capabilities), "Turn off" if key in business.declared_capabilities else "Turn on")}</div>'
        for key, (label, description) in _SERVICE_COPY.items()
    )
    return _page(
        "Business Services",
        f'<h1>Business Services</h1>{_help("Turn a service on to make it available for this business. Turning off a service stops that customer action.")}<section class="card">{rows}</section>',
        session=session,
        dev=request.app.state.settings.developer_tools_active,
    )


@router.get("/businesses/{business_id}/channels")
async def channels_page(business_id: str, request: Request) -> HTMLResponse:
    """Show only the business-owned, operator-safe channel view."""
    session = _require_session(request)
    registry = request.app.state.storage_runtime.business_registry
    business = await registry.get_business(business_id)
    if business is None:
        raise HTTPException(404, "This business could not be found.")
    channels = [
        channel for channel in await registry.list_channels() if channel.business_id == business_id
    ]
    rows = (
        "".join(
            f'<div class="row"><div><strong>{"Primary WhatsApp" if channel.is_primary else "Secondary WhatsApp"} {_inline_help("a WhatsApp channel", "A WhatsApp channel lets Ntheemba communicate for this business.")}</strong><p>{escape(channel.phone_e164)} · {"Connected" if channel.enabled else "Paused"}</p></div>{_action_form(session, _issue_action(request, session, business_id=business_id, kind="channel", resource_id=channel.channel_instance_id, enabled=not channel.enabled), "Pause" if channel.enabled else "Enable")}</div>'
            for channel in channels
        )
        or '<p class="notice">No WhatsApp channel is configured for this business.</p>'
    )
    add_form = (
        f'<form class="panel" method="post" action="/operator/businesses/{escape(business_id)}/channels">'
        f'<input type="hidden" name="csrf" value="{escape(session.csrf)}">'
        "<h2>Add WhatsApp</h2><label>WhatsApp number"
        '<input name="phone" inputmode="tel" placeholder="+260..." required></label>'
        "<button>Add WhatsApp</button></form>"
    )
    return _page(
        "WhatsApp & Channels",
        f'<h1>WhatsApp & Channels</h1>{_help("A WhatsApp channel is the business number Ntheemba uses. Pause a channel only when you want customer messages to stop reaching this business.")}<section class="card">{rows}</section>{add_form}',
        session=session,
        dev=request.app.state.settings.developer_tools_active,
    )


@router.post("/businesses/{business_id}/channels")
async def add_channel(business_id: str, request: Request) -> RedirectResponse:
    session = _require_session(request)
    form = _form(request, session, await request.body())
    registry = request.app.state.storage_runtime.business_registry
    if await registry.get_business(business_id) is None:
        raise HTTPException(404, "This business could not be found.")
    phone = form.get("phone", "").strip()
    channel_id = f"operator-{business_id}-{''.join(char for char in phone if char.isdigit())}"
    try:
        from ntheemba.domain.business import BusinessChannel

        await request.app.state.operator_control_plane.register_channel(
            BusinessChannel(channel_id, "operator_managed", business_id, phone),
            actor_id=session.actor,
            request_id=f"operator-ui-{token_urlsafe(12)}",
        )
    except (OperatorControlPlaneError, ValueError) as error:
        raise HTTPException(
            400, "This WhatsApp number could not be added. Check it and try again."
        ) from error
    return RedirectResponse(f"/operator/businesses/{business_id}/channels", status_code=303)


@router.get("/businesses/{business_id}/connections")
async def connections_page(business_id: str, request: Request) -> HTMLResponse:
    """Show connection state without endpoint or credential disclosure."""
    session = _require_session(request)
    registry = request.app.state.storage_runtime.business_registry
    business = await registry.get_business(business_id)
    if business is None:
        raise HTTPException(404, "This business could not be found.")
    integrations = await registry.list_integrations(business_id)
    rows = (
        "".join(
            f'<div class="row"><div><strong>TradeFlow</strong><p>{"Configured" if integration.enabled else "Paused"} · {"Testing" if integration.status == "testing" else "Connection saved"}</p><p class="muted">Services available: {len(integration.capabilities)}</p></div>{_action_form(session, _issue_action(request, session, business_id=business_id, kind="connection", resource_id=integration.integration_id, enabled=not integration.enabled), "Pause" if integration.enabled else "Enable")}</div>'
            for integration in integrations
        )
        or '<p class="notice">TradeFlow is not configured for this business.</p>'
    )
    add_form = (
        f'<details class="advanced-setup"><summary>Advanced connection setup</summary><p class="muted">Use this only when a business needs a TradeFlow connection. The address and credential reference are write-only and are never shown again.</p><form class="panel" method="post" action="/operator/businesses/{escape(business_id)}/connections">'
        f'<input type="hidden" name="csrf" value="{escape(session.csrf)}">'
        "<h2>Add TradeFlow connection</h2><label>Connection address"
        '<input name="base_url" type="url" placeholder="https://..." required></label>'
        "<label>Credential reference (optional, write-only)"
        '<input name="auth_reference" type="password" autocomplete="off"></label>'
        "<button>Save connection</button></form></details>"
    )
    catalogue = "Configured" if request.app.state.settings.ncpc_base_url else "Not configured"
    return _page(
        "Connections",
        f'<h1>Connections</h1>{_help("Connections let Ntheemba use approved business services. A saved connection is not a live availability check. Credentials and endpoint details are never shown here.")}<section class="card">{rows}</section>{add_form}<section class="card"><h2>Product Catalogue {_inline_help("the product catalogue", "This catalogue helps Ntheemba identify products.")}</h2><p>{catalogue}</p></section>',
        session=session,
        dev=request.app.state.settings.developer_tools_active,
    )


@router.post("/businesses/{business_id}/connections")
async def add_connection(business_id: str, request: Request) -> RedirectResponse:
    session = _require_session(request)
    form = _form(request, session, await request.body())
    registry = request.app.state.storage_runtime.business_registry
    business = await registry.get_business(business_id)
    if business is None:
        raise HTTPException(404, "This business could not be found.")
    try:
        from ntheemba.domain.business import BusinessIntegration

        await request.app.state.operator_control_plane.register_integration(
            BusinessIntegration(
                f"operator-tradeflow-{business_id}",
                business_id,
                "operator_managed",
                form.get("base_url", "").strip(),
                provider="tradeflow_http",
                auth_reference=form.get("auth_reference", "").strip(),
                capabilities=business.declared_capabilities,
            ),
            actor_id=session.actor,
            request_id=f"operator-ui-{token_urlsafe(12)}",
        )
    except (OperatorControlPlaneError, ValueError) as error:
        raise HTTPException(
            400, "This TradeFlow connection could not be saved. Check it and try again."
        ) from error
    return RedirectResponse(f"/operator/businesses/{business_id}/connections", status_code=303)


def _confirmation_copy(action: PendingOperatorAction) -> tuple[str, str, str]:
    verb = "enable" if action.enabled else "pause"
    if action.kind == "business":
        return "Business availability", f"{verb.title()} this business?", (
            "Pausing stops Ntheemba from serving this business until it is enabled again."
            if not action.enabled
            else "Enabling allows Ntheemba to serve this business again."
        )
    if action.kind == "service":
        label = _SERVICE_COPY[action.resource_id][0]
        return "Business service", f"{verb.title()} {label}?", (
            "Disabling this service stops that customer action for this business."
            if not action.enabled
            else "Enabling this service makes that customer action available."
        )
    if action.kind == "channel":
        return "WhatsApp channel", f"{verb.title()} this WhatsApp channel?", (
            "Pausing stops customer messages from reaching this business through this channel."
            if not action.enabled
            else "Enabling lets customer messages reach this business through this channel."
        )
    return "TradeFlow connection", f"{verb.title()} this TradeFlow connection?", (
        "Pausing prevents Ntheemba from using this saved TradeFlow connection."
        if not action.enabled
        else "Enabling allows Ntheemba to use this saved TradeFlow connection."
    )


@router.post("/confirm")
async def confirm_action(request: Request) -> HTMLResponse:
    session = _require_session(request)
    form = _form(request, session, await request.body())
    token = form.get("action_token", "")
    action = _pending_action(request, session, token)
    title, question, consequence = _confirmation_copy(action)
    cancel = f"/operator/businesses/{escape(action.business_id)}"
    if action.kind == "service":
        cancel += "/services"
    elif action.kind == "channel":
        cancel += "/channels"
    elif action.kind == "connection":
        cancel += "/connections"
    return _page(
        title,
        f'<h1>{escape(question)}</h1><p class="notice">! {escape(consequence)}</p><form class="panel" method="post" action="/operator/confirm/execute"><input type="hidden" name="csrf" value="{escape(session.csrf)}"><input type="hidden" name="action_token" value="{escape(token)}"><button>Confirm change</button> <a class="button" href="{cancel}">Cancel</a></form>',
        session=session,
        dev=request.app.state.settings.developer_tools_active,
    )


@router.post("/confirm/execute")
async def execute_confirmed_action(request: Request) -> RedirectResponse:
    session = _require_session(request)
    form = _form(request, session, await request.body())
    action = _consume_action(request, session, form.get("action_token", ""))
    registry = request.app.state.storage_runtime.business_registry
    business = await registry.get_business(action.business_id)
    if business is None:
        raise HTTPException(404, "This business could not be found.")
    try:
        if action.kind == "business":
            await request.app.state.operator_control_plane.set_business_enabled(
                action.business_id,
                enabled=action.enabled,
                actor_id=session.actor,
                request_id=f"operator-ui-{token_urlsafe(12)}",
            )
            destination = f"/operator/businesses/{action.business_id}"
        elif action.kind == "service":
            if action.resource_id not in _SERVICE_COPY:
                raise HTTPException(404, "This service could not be found.")
            await request.app.state.operator_control_plane.set_capability_enabled(
                action.business_id,
                action.resource_id,
                enabled=action.enabled,
                config=None,
                actor_id=session.actor,
                request_id=f"operator-ui-{token_urlsafe(12)}",
            )
            destination = f"/operator/businesses/{action.business_id}/services"
        elif action.kind == "channel":
            channel = await registry.get_channel(action.resource_id)
            if channel is None or channel.business_id != action.business_id:
                raise HTTPException(404, "This WhatsApp channel could not be found.")
            await request.app.state.operator_control_plane.register_channel(
                replace(channel, enabled=action.enabled),
                actor_id=session.actor,
                request_id=f"operator-ui-{token_urlsafe(12)}",
            )
            destination = f"/operator/businesses/{action.business_id}/channels"
        elif action.kind == "connection":
            integration = next(
                (item for item in await registry.list_integrations(action.business_id) if item.integration_id == action.resource_id),
                None,
            )
            if integration is None:
                raise HTTPException(404, "This TradeFlow connection could not be found.")
            await request.app.state.operator_control_plane.update_integration(
                action.business_id,
                action.resource_id,
                enabled=action.enabled,
                actor_id=session.actor,
                request_id=f"operator-ui-{token_urlsafe(12)}",
            )
            destination = f"/operator/businesses/{action.business_id}/connections"
        else:
            raise HTTPException(400, "This change is not recognised.")
    except (OperatorControlPlaneError, ValueError) as error:
        raise HTTPException(400, "This change could not be saved. Please try again.") from error
    return RedirectResponse(destination, status_code=303)


@router.get("/status")
async def status_page(request: Request) -> HTMLResponse:
    session = _require_session(request)
    businesses, integrations, channels = await _data(request)
    configured = sum(
        any(item.enabled and item.status == "active" for item in values)
        for values in integrations.values()
    )
    ncpc = "Configured" if request.app.state.settings.ncpc_base_url else "Not configured"
    return _page(
        "System Status",
        f'<h1>System Status <a class="help" href="#help">Help</a></h1><section class="grid"><article class="card"><h2>Ntheemba</h2><p>Configuration available</p></article><article class="card"><h2>Product Catalogue</h2><p>{ncpc}</p></article><article class="card"><h2>TradeFlow connections</h2><p>{configured} configured / {len(businesses) - configured} not configured</p></article><article class="card"><h2>WhatsApp channels</h2><p>{sum(getattr(item, "enabled", False) for item in channels)} active / {len(channels)} total</p></article></section><div id="help">{_help("This page shows saved configuration status in ordinary language. Developer tools contain technical diagnostics when they are enabled.")}</div>',
        session=session,
        dev=request.app.state.settings.developer_tools_active,
    )
