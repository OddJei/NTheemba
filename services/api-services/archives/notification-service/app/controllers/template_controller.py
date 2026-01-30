
from typing import Optional, Dict
from app.models.schemas import TemplateCreate
from app.services.template_service import TemplateService


async def upsert_template(payload: TemplateCreate, metadata: Optional[Dict] = None):
    svc = TemplateService()
    return await svc.create_or_update(payload, metadata=metadata)


async def get_template(name: str, metadata: Optional[Dict] = None):
    svc = TemplateService()
    return await svc.get_by_name(name, metadata=metadata)
