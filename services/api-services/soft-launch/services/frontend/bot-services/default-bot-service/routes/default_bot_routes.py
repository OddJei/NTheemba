"""Route declarations for the default bot (if exposed via HTTP API)."""

# Example FastAPI routes placeholder
from fastapi import APIRouter, Request
from controllers.default_bot_controller import DefaultBotController

router = APIRouter()
controller = DefaultBotController()


@router.post("/bot/handle")
async def handle_payload(request: Request):
    payload = await request.json()
    # session id from header or payload
    session_id = request.headers.get('X-Session-Id', 'anon')
    reply = controller.handle(payload, session_id=session_id)
    return reply
