"""Explicit browser authentication for developer-only tooling."""

from __future__ import annotations

from secrets import token_urlsafe
from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ntheemba.devtools.security import developer_session_cookie_name

router = APIRouter(prefix="/dev", tags=["developer-auth"], include_in_schema=False)

_LOGIN_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ntheemba Developer Login</title>
  <style nonce="__CSP_NONCE__">
    :root { color-scheme: dark; font-family: Inter, system-ui, sans-serif; }
    body { margin: 0; min-height: 100vh; display: grid; place-items: center;
      background: #101217; color: #eef1f6; }
    main { width: min(92vw, 30rem); border: 1px solid #2c323d;
      border-radius: .8rem; padding: 1.2rem; background: #151920; }
    h1 { font-size: 1.2rem; margin-top: 0; }
    p { color: #aeb7c6; line-height: 1.45; }
    label { display: grid; gap: .4rem; margin: 1rem 0; }
    input, button { width: 100%; box-sizing: border-box; border: 1px solid #3b4350;
      border-radius: .45rem; padding: .7rem; background: #191d25; color: inherit; }
    button { cursor: pointer; border-color: #4d70a8; }
    .error { color: #ff8793; }
  </style>
</head>
<body>
<main>
  <h1>Ntheemba Developer Access</h1>
  <p>Authenticate explicitly to open the developer console and simulators.
    The raw developer token is not stored in browser JavaScript storage.</p>
  __ERROR__
  <form method="post" action="/dev/auth/session" autocomplete="off">
    <input type="hidden" name="next" value="__NEXT__">
    <label>Developer token
      <input name="token" type="password" autocomplete="current-password" required autofocus>
    </label>
    <button type="submit">Sign in</button>
  </form>
</main>
</body>
</html>"""

_ALLOWED_NEXT = {
    "/dev/console",
    "/dev/pipeline",
    "/dev/simulator",
    "/dev/simulator/workspace",
    "/dev/simulation-lab",
}


def _safe_next(value: str | None) -> str:
    return value if value in _ALLOWED_NEXT else "/dev/console"


@router.get("/login", response_class=HTMLResponse)
async def developer_login(request: Request) -> HTMLResponse:
    nonce = token_urlsafe(18)
    next_path = _safe_next(request.query_params.get("next"))
    error = (
        '<p class="error">Authentication failed.</p>'
        if request.query_params.get("error") == "invalid"
        else ""
    )
    html = (
        _LOGIN_HTML.replace("__CSP_NONCE__", nonce)
        .replace("__NEXT__", next_path)
        .replace("__ERROR__", error)
    )
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                f"default-src 'none'; style-src 'nonce-{nonce}'; "
                "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
            ),
        },
    )


@router.post("/auth/session")
async def create_developer_session(request: Request) -> RedirectResponse:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/x-www-form-urlencoded":
        return RedirectResponse("/dev/login?error=invalid", status_code=303)

    body = (await request.body()).decode("utf-8", errors="replace")
    form = parse_qs(body, keep_blank_values=True)
    supplied = (form.get("token") or [""])[0].strip()
    next_path = _safe_next((form.get("next") or [""])[0])
    policy = request.app.state.dev_tools_security_policy
    if not policy.token_required or not policy.token_is_valid(supplied):
        return RedirectResponse(
            f"/dev/login?error=invalid&next={next_path}",
            status_code=303,
        )

    session_token = request.app.state.dev_tools_sessions.issue()
    response = RedirectResponse(next_path, status_code=303)
    response.set_cookie(
        developer_session_cookie_name(),
        session_token,
        max_age=request.app.state.settings.dev_tools_session_ttl_seconds,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/dev",
    )
    return response


@router.get("/auth/session")
async def developer_session_entry() -> RedirectResponse:
    """Guide direct browser visits to the sign-in page; sessions are POST-only."""
    return RedirectResponse("/dev/login", status_code=303)


@router.post("/auth/logout")
async def destroy_developer_session(request: Request) -> RedirectResponse:
    cookie_name = developer_session_cookie_name()
    request.app.state.dev_tools_sessions.revoke(request.cookies.get(cookie_name))
    response = RedirectResponse("/dev/login", status_code=303)
    response.delete_cookie(cookie_name, path="/dev")
    return response
