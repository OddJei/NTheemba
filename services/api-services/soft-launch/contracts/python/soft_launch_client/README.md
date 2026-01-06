# soft_launch_client (reference)

A small reference implementation of the **Transport Plugin** pattern used by soft-launch services.

## What it gives you

- `AsyncServiceClient` with a middleware chain
- `HttpxAsyncTransport` (real HTTP) and `MockTransport` (tests)
- Middleware examples: correlation, idempotency, auth, retry, observability
- A small default `OPERATION_MAP`

## Install deps (per-service)

- `pip install httpx`

## Quick usage

```python
import httpx
from soft_launch_client.client import AsyncServiceClient
from soft_launch_client.operation_map import OPERATION_MAP
from soft_launch_client.transports.httpx_async import HttpxAsyncTransport
from soft_launch_client.middleware.correlation import CorrelationMiddleware
from soft_launch_client.middleware.idempotency import IdempotencyMiddleware
from soft_launch_client.middleware.retry import RetryMiddleware

base_urls = {
    "cart": "http://cart-service:8000",
    "order": "http://order-service:8000",
    "payment-revenue": "http://payment-revenue:8000",
    "delivery": "http://delivery-service:8000",
    "notification": "http://notification-service:8000",
}

async_client = httpx.AsyncClient()
transport = HttpxAsyncTransport(base_urls=base_urls, http=async_client)

client = AsyncServiceClient(
    operation_map=OPERATION_MAP,
    transport=transport,
    middlewares=[
        CorrelationMiddleware(),
        IdempotencyMiddleware(),
        RetryMiddleware(),
    ],
)

# Call by operation name; the map resolves service/method/path
resp = await client.call(
    operation="order.create",
    body={"business_id": "...", "user_phone": "+260...", "items": []},
    context={"correlation_id": "req-123"},
)
```

Close the underlying http client on shutdown:

```python
await async_client.aclose()
```
