# Phase 11.7 — Developer Tooling Security

Phase 11.7 hardens the trace API, browser console, and fake-dependency controls added in Phases 11.4–11.6. It does not change customer workflows or production adapters.

## Security boundary

Developer tooling is registered only when both conditions are true:

1. `NTHEEMBA_ENVIRONMENT` is `development` or `test`.
2. `NTHEEMBA_DEV_TOOLS_ENABLED` is `true`.

Staging and production do not register `/dev/*` routes and do not instantiate the in-memory trace store or fake-dependency controller.

## Network restriction

The socket peer must belong to an explicitly allowed IP network. The default is loopback only:

```env
NTHEEMBA_DEV_TOOLS_ALLOWED_NETWORKS=127.0.0.0/8,::1/128
```

`X-Forwarded-For` and similar forwarding headers are deliberately ignored. This prevents a caller from claiming to be local by supplying a forged header.

To permit a LAN or other non-loopback network, add its CIDR and configure a token:

```env
NTHEEMBA_DEV_TOOLS_ALLOWED_NETWORKS=127.0.0.0/8,::1/128,192.168.1.0/24
NTHEEMBA_DEV_TOOLS_TOKEN=replace-with-at-least-32-random-characters
```

Application startup validation rejects non-loopback networks when no developer token is configured.

## Authentication

When `NTHEEMBA_DEV_TOOLS_TOKEN` is configured, all developer JSON APIs require either:

```http
Authorization: Bearer <token>
```

or:

```http
X-Ntheemba-Dev-Token: <token>
```

Token comparison uses constant-time comparison. Missing or invalid credentials return `401` with a generic response and never echo the supplied value.

The `/dev/console` HTML shell remains accessible to an approved network so a developer can enter the token. The token is stored only in `sessionStorage`, applies only to the current browser tab, is sent as a Bearer header, and is never inserted into the URL or rendered into the HTML response.

## Browser request protection

Developer requests are rejected when:

- `Origin` identifies a different origin;
- `Origin` is `null`;
- `Sec-Fetch-Site` reports `cross-site`.

CLI requests without browser-origin headers remain supported. The application does not enable permissive CORS for developer routes.

## Response hardening

Every `/dev/*` response, including security errors, receives defensive headers:

- `Cache-Control: no-store`
- `Pragma: no-cache`
- `Expires: 0`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- restrictive `Permissions-Policy`
- `Cross-Origin-Resource-Policy: same-origin`

The developer console now uses a per-response CSP nonce. Inline scripts and styles are authorized only by that nonce; `unsafe-inline` is no longer used. Framing, forms, objects, external scripts, and external styles remain blocked.

## Trace redaction

Trace attributes are copied through a bounded redaction layer before HTTP exposure. Secret-like keys—including passwords, tokens, API keys, authorization values, cookies, credentials, and private keys—are replaced with:

```text
[REDACTED]
```

Nested values are redacted recursively. Long strings, deep objects, large collections, and binary values are bounded so the developer API cannot accidentally return uncontrolled payloads.

## OpenAPI exposure

All developer routes are excluded from the generated OpenAPI schema. This reduces accidental discovery through `/docs` while preserving direct local use.

## Configuration

```env
NTHEEMBA_DEV_TOOLS_ENABLED=true
NTHEEMBA_DEV_TOOLS_ALLOWED_NETWORKS=127.0.0.0/8,::1/128
NTHEEMBA_DEV_TOOLS_TOKEN=
```

Recommended local modes:

### Local machine only

Keep the default loopback networks. A token is optional.

### LAN or reverse-proxy access

Use a strong token and an explicit narrow CIDR. When a reverse proxy connects to Ntheemba through loopback, always configure a token because the application correctly sees the proxy as the socket peer.

### Disable developer tooling

```env
NTHEEMBA_DEV_TOOLS_ENABLED=false
```

## Files added

- `ntheemba/devtools/security.py`
- `ntheemba/devtools/redaction.py`
- `tests/test_dev_security.py`
- `tests/unit/devtools/test_redaction.py`

## Files updated

- `ntheemba/config.py`
- `ntheemba/main.py`
- `ntheemba/api/routes/dev_console.py`
- `ntheemba/api/routes/dev_dependencies.py`
- `ntheemba/api/routes/dev_tracing.py`
- `.env.example`
- `README.md`

## Validation

Phase 11.7 completes with:

```text
263 tests passed
Ruff check passed
Ruff format check passed
MyPy strict passed
```

The remaining test warning is the existing FastAPI/Starlette TestClient dependency-transition warning and is unrelated to Phase 11.7 behavior.
