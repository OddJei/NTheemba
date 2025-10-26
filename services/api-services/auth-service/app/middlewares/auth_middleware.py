from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.utils.jwt_utils import decode_jwt

class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/auth") or request.url.path.startswith("/otp"):
            return await call_next(request)  # public routes

        token = request.headers.get("Authorization")
        if not token or not token.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid token")

        payload = decode_jwt(token.split(" ")[1])
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        request.state.user = payload
        return await call_next(request)
