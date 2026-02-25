import secrets
import time
import os
from fastapi import Response, Cookie, HTTPException
from .dependencies import get_redis

SESSION_TTL = int(os.getenv("SESSION_TTL", "3600"))

async def create_session(response: Response, user_id: str, redis=None) -> str:
    if redis is None:
        redis = get_redis()
    session_id = secrets.token_urlsafe(32)
    key = f"session:{session_id}"
    data = {"user_id": user_id, "created": int(time.time())}
    await redis.hset(key, mapping=data)
    await redis.expire(key, SESSION_TTL)
    response.set_cookie("session_id", session_id, httponly=True, secure=False, samesite="lax")
    return session_id

async def get_current_session(session_id: str = Cookie(None), redis=None):
    if not session_id:
        raise HTTPException(status_code=401, detail="Missing session cookie")
    if redis is None:
        redis = get_redis()
    key = f"session:{session_id}"
    exists = await redis.exists(key)
    if not exists:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    data = await redis.hgetall(key)
    return {"session_id": session_id, "user": data.get("user_id")}
