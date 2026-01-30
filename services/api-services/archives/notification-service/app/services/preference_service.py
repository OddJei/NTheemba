from app.models.db import AsyncSessionLocal
from app.models.user_preferences import UserPreference
from app.models.schemas import PreferenceUpdate
from sqlalchemy import select


class PreferenceService:
    def __init__(self):
        self.db = None

    async def update_or_create(self, payload: PreferenceUpdate, metadata: dict | None = None):
        async with AsyncSessionLocal() as session:
            async with session.begin():
                result = await session.execute(select(UserPreference).filter_by(user_id=payload.user_id))
                p = result.scalar_one_or_none()
                if p:
                    if payload.preferred_channel is not None:
                        p.preferred_channel = payload.preferred_channel
                    if payload.opt_in is not None:
                        p.opt_in = payload.opt_in
                else:
                    p = UserPreference(user_id=payload.user_id, preferred_channel=payload.preferred_channel, opt_in=(payload.opt_in if payload.opt_in is not None else True))
                    session.add(p)
            await session.refresh(p)
            # audit
            try:
                import asyncio
                from app.utils.audit import log_event

                asyncio.create_task(
                    log_event(
                        service="notification-service",
                        event_type="preference_updated",
                        actor_id=payload.user_id,
                        entity_type="user_preference",
                        entity_id=p.id,
                        payload={"preferred_channel": p.preferred_channel, "opt_in": p.opt_in},
                        metadata=(metadata or {}),
                    )
                )
            except Exception:
                pass

            return p

    async def get_by_user(self, user_id: str, metadata: dict | None = None):
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(UserPreference).filter_by(user_id=user_id))
            p = result.scalar_one_or_none()
            try:
                import asyncio
                from app.utils.audit import log_event

                if p:
                    asyncio.create_task(
                        log_event(
                            service="notification-service",
                            event_type="preference_viewed",
                            actor_id=user_id,
                            entity_type="user_preference",
                            entity_id=p.id,
                            payload={"preferred_channel": p.preferred_channel, "opt_in": p.opt_in},
                            metadata=(metadata or {}),
                        )
                    )
            except Exception:
                pass
            return p
