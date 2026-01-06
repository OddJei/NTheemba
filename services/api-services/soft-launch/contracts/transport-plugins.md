# Transport Plugins (Pluggable Backend Calls)

Goal: Every service should call other services through a single internal API:
- `await client.call(service, operation, body=...)`
and the *transport* (HTTP, mock, direct in-process, queue) is provided by plugins.

This makes the backend pluggable:
- swap HTTP ↔ mock for tests
- add cross-cutting behavior (auth, retries, tracing) as middleware
- evolve HTTP → async messaging later without rewriting business logic

## 1) Core idea

### A) Domain/business code never calls HTTP directly
Business modules call a **ServiceClient** instead of `httpx` directly.

### B) Plugins wrap every call
A plugin can:
- add headers (correlation / idempotency)
- attach service-to-service auth
- handle retries/backoff
- record audit logs
- route to HTTP vs mock

## 2) Minimal interfaces (async)

### Request / Response
- Request: `{ service, operation, method, path, query, headers, body, timeout, context }`
- Response: `{ status, headers, body }`

### Transport
- `async send(request) -> response`

### Middleware
- `async handle(request, next) -> response`

Execution order:
`mw1 -> mw2 -> transport.send -> mw2 -> mw1`

## 3) Recommended plugin set (soft launch)

- Transport:
    - `HttpxAsyncTransport` (default): talks to other services over HTTP
    - `MockTransport` (tests): static responses or local fixtures

- Middleware:
    - `CorrelationMiddleware`: ensures `X-Correlation-Id` exists on all outbound calls
    - `IdempotencyMiddleware`: adds `X-Idempotency-Key` to unsafe retryable calls (POST/PUT)
    - `AuthMiddleware`: attaches service-to-service token
    - `RetryMiddleware`: retries transient failures (timeouts/502/503/504)
    - `ObservabilityMiddleware`: logs duration + status + service/operation

## 4) Naming conventions

- `service` uses soft-launch names: `cart`, `order`, `payment-revenue`, `delivery`, `notification`, `affiliate-engine`, `msme-engine`, `bot-session`, `catalog-inventory`
- `operation` is stable (not a URL), e.g.:
    - `cart.create`, `cart.add_item`, `cart.checkout`
    - `order.create`, `order.set_status`
    - `payment.initiate`, `payment.verify`
    - `delivery.generate_code`, `delivery.confirm`
    - `notify.send`

The client maps `operation -> { service, method, path }` via an `operation_map`.

## 5) Tiny operation_map (example)

```python
OPERATION_MAP = {
        "cart.create": {"service": "cart", "method": "POST", "path": "/cart/create"},
        "cart.add_item": {"service": "cart", "method": "POST", "path": "/cart/{cart_id}/add"},
        "cart.checkout": {"service": "cart", "method": "POST", "path": "/cart/{cart_id}/checkout"},
        "order.create": {"service": "order", "method": "POST", "path": "/order/create"},
        "order.set_status": {"service": "order", "method": "PUT", "path": "/order/{order_id}/status"},
        "payment.initiate": {"service": "payment-revenue", "method": "POST", "path": "/payment/initiate"},
        "payment.verify": {"service": "payment-revenue", "method": "POST", "path": "/payment/{payment_id}/verify"},
        "delivery.generate_code": {"service": "delivery", "method": "POST", "path": "/delivery/generate"},
        "delivery.confirm": {"service": "delivery", "method": "POST", "path": "/delivery/confirm"},
        "notify.send": {"service": "notification", "method": "POST", "path": "/notify/send"},
}
```

## 6) Integration requirements

- Every outbound call MUST propagate `X-Correlation-Id`.
- For POST/PUT that can be retried, the client SHOULD attach `X-Idempotency-Key`.
- Services receiving these headers SHOULD log and/or persist them (outbox, audit, etc.).

## 7) Reference implementation (async httpx)

A reusable reference implementation lives here:

- `api-services/soft-launch/contracts/python/soft_launch_client/`

It provides:
- `AsyncServiceClient` using `httpx.AsyncClient`
- pluggable middleware chain
- `HttpxAsyncTransport` + `MockTransport`
- a small default `operation_map`

## 8) FastAPI wiring (example)

Create the shared client once at startup and close it on shutdown.

```python
import httpx
from fastapi import FastAPI

from soft_launch_client.client import AsyncServiceClient
from soft_launch_client.operation_map import OPERATION_MAP
from soft_launch_client.transports.httpx_async import HttpxAsyncTransport
from soft_launch_client.middleware.correlation import CorrelationMiddleware
from soft_launch_client.middleware.idempotency import IdempotencyMiddleware
from soft_launch_client.middleware.retry import RetryMiddleware

app = FastAPI()

@app.on_event("startup")
async def startup():
    app.state.http = httpx.AsyncClient()
    app.state.service_client = AsyncServiceClient(
        operation_map=OPERATION_MAP,
        transport=HttpxAsyncTransport(
            base_urls={
                "cart": "http://cart-service:8000",
                "order": "http://order-service:8000",
                "payment-revenue": "http://payment-revenue:8000",
                "delivery": "http://delivery-service:8000",
                "notification": "http://notification-service:8000",
            },
            http=app.state.http,
        ),
        middlewares=[CorrelationMiddleware(), IdempotencyMiddleware(), RetryMiddleware()],
    )

@app.on_event("shutdown")
async def shutdown():
    await app.state.http.aclose()
```