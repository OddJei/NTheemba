"""Security boundary for developer-only HTTP tooling."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network, ip_address
from secrets import token_urlsafe
from urllib.parse import quote, urlsplit

from fastapi import Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from ntheemba.config import Settings

logger = logging.getLogger("ntheemba.devtools.security")

_DEV_PREFIX = "/dev"
_LOGIN_PATH = "/dev/login"
_SESSION_PATH = "/dev/auth/session"
_CONSOLE_PATHS = frozenset(
    {
        "/dev/console",
        "/dev/pipeline",
        "/dev/simulator",
        "/dev/simulator/workspace",
        "/dev/simulation-lab",
    }
)
_SESSION_COOKIE = "ntheemba_dev_session"
_SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "Expires": "0",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": (
        "camera=(), microphone=(), geolocation=(), payment=(), usb=(), serial=()"
    ),
    "Cross-Origin-Resource-Policy": "same-origin",
}

IPAddress = IPv4Address | IPv6Address
IPNetwork = IPv4Network | IPv6Network


@dataclass(frozen=True, slots=True)
class DeveloperToolsSecurityPolicy:
    """Immutable access policy derived from validated application settings."""

    environment: str
    allowed_networks: tuple[IPNetwork, ...]
    token: str | None

    @classmethod
    def from_settings(cls, settings: Settings) -> DeveloperToolsSecurityPolicy:
        token = (
            settings.dev_tools_token.get_secret_value()
            if settings.dev_tools_token is not None
            else None
        )
        return cls(
            environment=settings.environment,
            allowed_networks=settings.parsed_dev_tools_networks,
            token=token,
        )

    @property
    def token_required(self) -> bool:
        return self.token is not None

    def client_is_allowed(self, host: str | None) -> bool:
        """Check the socket peer only; forwarded IP headers are intentionally ignored."""

        if not host:
            return False
        if self.environment == "test" and host == "testclient":
            return True
        try:
            address: IPAddress = ip_address(host)
        except ValueError:
            return False
        return any(address in network for network in self.allowed_networks)

    def token_is_valid(self, supplied: str | None) -> bool:
        if self.token is None:
            return True
        if supplied is None:
            return False
        return hmac.compare_digest(supplied.encode("utf-8"), self.token.encode("utf-8"))


@dataclass(slots=True)
class DeveloperToolsSessionStore:
    """Process-local opaque developer sessions; never stores the browser token itself."""

    ttl_seconds: int
    _sessions: dict[str, float] = field(default_factory=dict, init=False)

    @staticmethod
    def _fingerprint(session_token: str) -> str:
        return hashlib.sha256(session_token.encode("utf-8")).hexdigest()

    def issue(self) -> str:
        self._purge_expired()
        session_token = token_urlsafe(32)
        self._sessions[self._fingerprint(session_token)] = time.time() + self.ttl_seconds
        return session_token

    def is_valid(self, session_token: str | None) -> bool:
        if not session_token:
            return False
        expires_at = self._sessions.get(self._fingerprint(session_token))
        if expires_at is None:
            return False
        if expires_at <= time.time():
            self._sessions.pop(self._fingerprint(session_token), None)
            return False
        return True

    def revoke(self, session_token: str | None) -> None:
        if session_token:
            self._sessions.pop(self._fingerprint(session_token), None)

    def _purge_expired(self) -> None:
        now = time.time()
        expired = [key for key, expires_at in self._sessions.items() if expires_at <= now]
        for key in expired:
            self._sessions.pop(key, None)


class DeveloperToolsSecurityMiddleware(BaseHTTPMiddleware):
    """Protect `/dev/*` with network, token, origin, and cache controls."""

    def __init__(
        self, app: ASGIApp, policy: DeveloperToolsSecurityPolicy, sessions: DeveloperToolsSessionStore
    ) -> None:
        super().__init__(app)
        self._policy = policy
        self._sessions = sessions

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if not _is_developer_path(request.url.path):
            return await call_next(request)

        client_host = request.client.host if request.client is not None else None
        if not self._policy.client_is_allowed(client_host):
            logger.warning(
                "Denied developer tooling request from unapproved peer",
                extra={"path": request.url.path, "client_host": client_host or "unknown"},
            )
            return _secured_error(403, "Developer tooling access denied.")

        if not _origin_is_allowed(request) and not _is_null_origin_login(request):
            logger.warning(
                "Denied cross-origin developer tooling request",
                extra={"path": request.url.path, "client_host": client_host or "unknown"},
            )
            return _secured_error(403, "Developer tooling access denied.")

        if _is_public_auth_request(request):
            response = await call_next(request)
            _apply_security_headers(response)
            return response
        if self._policy.token_required and not self._request_is_authenticated(request):
            logger.warning("Denied unauthenticated developer tooling request", extra={"path": request.url.path, "client_host": client_host or "unknown"})
            if request.method == "GET" and request.url.path in _CONSOLE_PATHS:
                response = RedirectResponse(url=f"{_LOGIN_PATH}?next={quote(request.url.path, safe='/')}", status_code=303)
                _apply_security_headers(response)
                return response
            return _secured_error(401, "Developer tooling authentication required.", authenticate=True)

        response = await call_next(request)
        _apply_security_headers(response)
        return response

    def _request_is_authenticated(self, request: Request) -> bool:
        supplied_token = _extract_token(request)
        if supplied_token is not None and self._policy.token_is_valid(supplied_token):
            return True
        return self._sessions.is_valid(request.cookies.get(_SESSION_COOKIE))


def developer_session_cookie_name() -> str:
    return _SESSION_COOKIE


def _is_public_auth_request(request: Request) -> bool:
    return (request.method == "GET" and request.url.path == _LOGIN_PATH) or (
        request.method == "POST" and request.url.path == _SESSION_PATH
    )


def _is_null_origin_login(request: Request) -> bool:
    """Permit only the token-bearing local sign-in form for privacy-mode browsers.

    The developer token remains mandatory and all already-authenticated /dev
    routes retain strict same-origin enforcement.
    """

    return (
        request.method == "POST"
        and request.url.path == _SESSION_PATH
        and request.headers.get("origin", "").lower() == "null"
    )


def _is_developer_path(path: str) -> bool:
    return path == _DEV_PREFIX or path.startswith(f"{_DEV_PREFIX}/")


def _extract_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "")
    scheme, separator, credentials = authorization.partition(" ")
    if separator and scheme.lower() == "bearer" and credentials.strip():
        return credentials.strip()
    explicit = request.headers.get("x-ntheemba-dev-token")
    return explicit.strip() if explicit and explicit.strip() else None


def _origin_is_allowed(request: Request) -> bool:
    if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
        return False

    origin = request.headers.get("origin")
    if origin is None:
        return True
    if origin == "null":
        return False

    parsed = urlsplit(origin)
    request_host = request.headers.get("host", "").lower()
    return (
        parsed.scheme.lower() == request.url.scheme.lower()
        and parsed.netloc.lower() == request_host
        and parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment
    )


def _secured_error(
    status_code: int,
    detail: str,
    *,
    authenticate: bool = False,
) -> JSONResponse:
    response = JSONResponse(status_code=status_code, content={"detail": detail})
    if authenticate:
        response.headers["WWW-Authenticate"] = 'Bearer realm="ntheemba-devtools"'
    _apply_security_headers(response)
    return response


def _apply_security_headers(response: Response) -> None:
    for name, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
