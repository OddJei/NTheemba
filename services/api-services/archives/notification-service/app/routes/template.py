from fastapi import APIRouter, HTTPException, Request, Header
from app.models.schemas import TemplateCreate, TemplateRead
from app.controllers.template_controller import upsert_template, get_template

router = APIRouter()


@router.post("/notification/template", response_model=TemplateRead)
async def api_upsert_template(payload: TemplateCreate, request: Request, x_request_id: str | None = Header(None)):
    metadata = {"request_id": x_request_id or "", "ip": request.client.host if request.client else ""}
    t = await upsert_template(payload, metadata=metadata)
    if not t:
        raise HTTPException(status_code=500, detail="failed to upsert template")
    return t


@router.get("/notification/template/{name}", response_model=TemplateRead)
async def api_get_template(name: str, request: Request, x_request_id: str | None = Header(None)):
    metadata = {"request_id": x_request_id or "", "ip": request.client.host if request.client else ""}
    t = await get_template(name, metadata=metadata)
    if not t:
        raise HTTPException(status_code=404, detail="template not found")
    return t
