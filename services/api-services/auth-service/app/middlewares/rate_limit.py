import time
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

RATE_LIMIT = 100  # requests
WINDOW = 60       # seconds
requests_log = {}

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip = request.client.host
        now = time.time()
        window_start = now - WINDOW

        if ip not in requests_log:
            requests_log[ip] = []
        requests_log[ip] = [t for t in requests_log[ip] if t > window_start]

        if len(requests_log[ip]) >= RATE_LIMIT:
            raise HTTPException(status_code=429, detail="Too many requests")

        requests_log[ip].append(now)
        return await call_next(request)
