from fastapi import APIRouter, HTTPException, Request, Header
from app.models.schemas import PreferenceUpdate, PreferenceRead
from app.controllers.preference_controller import update_preference, get_preference

router = APIRouter()


@router.put("/notification/preferences/{id}", response_model=PreferenceRead)
async def api_update_preference(id: str, payload: PreferenceUpdate, request: Request, x_request_id: str | None = Header(None)):
    # note: id is unused because we identify by user_id in payload
    metadata = {"request_id": x_request_id or "", "ip": request.client.host if request.client else ""}
    pref = await update_preference(payload, metadata=metadata)
    if not pref:
        raise HTTPException(status_code=500, detail="failed to update preference")
    return pref


@router.get("/notification/preferences/user/{user_id}", response_model=PreferenceRead)
async def api_get_preference(user_id: str, request: Request, x_request_id: str | None = Header(None)):
    metadata = {"request_id": x_request_id or "", "ip": request.client.host if request.client else ""}
    p = await get_preference(user_id, metadata=metadata)
    if not p:
        raise HTTPException(status_code=404, detail="preference not found")
    return p
