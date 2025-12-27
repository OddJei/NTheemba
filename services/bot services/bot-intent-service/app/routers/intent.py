from fastapi import APIRouter, HTTPException, status

from ..models.schemas import IntentRequest, IntentResponse
from ..services.intent_service import AttachmentLimitError, service

router = APIRouter(tags=["intent"])


async def _resolve(payload: IntentRequest) -> IntentResponse:
    try:
        return await service.resolve(payload)
    except AttachmentLimitError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/v1/intent/resolve", response_model=IntentResponse, status_code=status.HTTP_200_OK)
async def resolve_intent_v1(payload: IntentRequest) -> IntentResponse:
    return await _resolve(payload)


# Backward-compatible alias
@router.post("/intent/resolve", response_model=IntentResponse, status_code=status.HTTP_200_OK)
async def resolve_intent(payload: IntentRequest) -> IntentResponse:
    return await _resolve(payload)
