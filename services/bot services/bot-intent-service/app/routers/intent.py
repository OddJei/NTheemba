from fastapi import APIRouter, HTTPException, status

from ..models.schemas import IntentRequest, IntentResponse
from ..services.intent_service import AttachmentLimitError, service

router = APIRouter(prefix="/intent", tags=["intent"])


@router.post("/resolve", response_model=IntentResponse, status_code=status.HTTP_200_OK)
async def resolve_intent(payload: IntentRequest) -> IntentResponse:
    try:
        return await service.resolve(payload)
    except AttachmentLimitError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
