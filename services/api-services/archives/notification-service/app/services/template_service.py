from app.models.db import AsyncSessionLocal
from app.models.templates import Template
from app.models.schemas import TemplateCreate
from sqlalchemy import select
from app.utils.audit import log_event
import asyncio




class TemplateService:
    def __init__(self):
        self.db = None

    async def create_or_update(self, payload: TemplateCreate, metadata: dict | None = None):
        from fastapi.concurrency import run_in_threadpool

        async with AsyncSessionLocal() as session:
            async with session.begin():
                result = await session.execute(select(Template).filter_by(name=payload.name))
                t = result.scalar_one_or_none()
                created = False
                if t:
                    t.channel = payload.channel
                    t.content = payload.content
                else:
                    created = True
                    t = Template(name=payload.name, channel=payload.channel, content=payload.content)
                    session.add(t)
            await session.refresh(t)
            # audit: don't block the response
            try:
                evt = "template_created" if created else "template_updated"
                asyncio.create_task(
                    log_event(
                        service="notification-service",
                        event_type=evt,
                        actor_id="system",
                        entity_type="template",
                        entity_id=t.id,
                        payload={"name": t.name, "channel": t.channel},
                        metadata=(metadata or {}),
                    )
                )
            except Exception:
                pass

            return t

    async def get_by_name(self, name: str, metadata: dict | None = None):
        from fastapi.concurrency import run_in_threadpool

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Template).filter_by(name=name))
            t = result.scalar_one_or_none()
            try:
                if t:
                    asyncio.create_task(
                        log_event(
                            service="notification-service",
                            event_type="template_viewed",
                            actor_id="system",
                            entity_type="template",
                            entity_id=t.id,
                            payload={"name": t.name},
                            metadata=(metadata or {}),
                        )
                    )
            except Exception:
                pass
            return t
