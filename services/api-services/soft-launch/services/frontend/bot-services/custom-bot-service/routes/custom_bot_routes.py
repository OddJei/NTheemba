"""HTTP routes for custom bot (FastAPI example)."""
from fastapi import APIRouter, Request
from controllers.custom_bot_controller import CustomBotController

router = APIRouter()
controller = CustomBotController()


@router.post("/custom-bot/handle")
async def handle_payload(request: Request):
    payload = await request.json()
    session_id = request.headers.get('X-Session-Id', 'anon')
    reply = controller.handle(payload, session_id=session_id)
    return reply
