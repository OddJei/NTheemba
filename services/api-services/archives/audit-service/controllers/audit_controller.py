from fastapi import Request, HTTPException, Query
from core.database import SessionLocal
from services.audit_service import ingest_event, fetch_audit, list_audits
from utils.validators import validate_event_shape
from datetime import datetime
from typing import Optional


async def ingest_events(request: Request):
    body = await request.json()
    # Accept array or single
    events = body if isinstance(body, list) else [body]

    db = SessionLocal()
    try:
        created = []
        for ev in events:
            if not validate_event_shape(ev):
                raise HTTPException(status_code=400, detail='invalid_event_shape')
            created_id = ingest_event(db, ev)
            created.append(created_id)
        return {"ok": True, "created": created}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


def get_audit(audit_id: str):
    db = SessionLocal()
    try:
        record = fetch_audit(db, audit_id)
        if not record:
            raise HTTPException(status_code=404, detail='not_found')
        return record
    finally:
        db.close()


def query_audits(
    service: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    actor_id: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    from_ts: Optional[str] = Query(None),
    to_ts: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=1000),
):
    db = SessionLocal()
    try:
        ffrom = datetime.fromisoformat(from_ts) if from_ts else None
        tto = datetime.fromisoformat(to_ts) if to_ts else None
        return list_audits(db, service=service, event_type=event_type, actor_id=actor_id,
                          entity_type=entity_type, entity_id=entity_id, severity=severity,
                          from_ts=ffrom, to_ts=tto, page=page, size=size)
    finally:
        db.close()
