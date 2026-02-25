from fastapi import APIRouter, Response, Depends
import httpx
from .auth import create_session, get_current_session
from .dependencies import get_redis, BACKEND_BASE_URL

router = APIRouter()


@router.post("/login")
async def login(response: Response, payload: dict, redis=Depends(get_redis)):
    # very small demo: accept any username and create a session
    username = payload.get("username") or "demo-user"
    session_id = await create_session(response=response, user_id=username, redis=redis)
    return {"ok": True, "session_id": session_id}


@router.get("/dashboard")
async def dashboard(session=Depends(get_current_session), redis=Depends(get_redis)):
    # Aggregate a small piece of data from the backend service
    backend_health = {"error": "unreachable"}
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{BACKEND_BASE_URL}/")
            r.raise_for_status()
            if "application/json" in r.headers.get("content-type", ""):
                backend_health = r.json()
            else:
                backend_health = {"text": r.text}
    except Exception as exc:
        backend_health = {"error": str(exc)}

    return {"user": session["user"], "backend": backend_health}
