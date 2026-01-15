from datetime import datetime
from models.audit import AuditLog
from sqlalchemy.orm import Session
import hashlib
from typing import List, Optional, Dict, Any


def audit_to_dict(audit: AuditLog) -> Dict[str, Any]:
    return {
        'id': audit.id,
        'occurred_at': audit.occurred_at.isoformat() if audit.occurred_at else None,
        'service': audit.service,
        'event_type': audit.event_type,
        'actor_id': audit.actor_id,
        'entity_type': audit.entity_type,
        'entity_id': audit.entity_id,
        'severity': audit.severity,
        'payload': audit.payload,
        'metadata': getattr(audit, 'metadata_', None),
        'checksum': audit.checksum,
        'archived': audit.archived,
        'created_at': audit.created_at.isoformat() if audit.created_at else None,
    }

def _compute_checksum(payload: dict) -> str:
    s = repr(payload).encode('utf-8')
    return hashlib.sha256(s).hexdigest()

def ingest_event(db: Session, event: dict) -> str:
    # minimal validation
    if 'service' not in event or 'event_type' not in event or 'payload' not in event:
        raise ValueError('missing required fields: service,event_type,payload')

    audit = AuditLog(
        occurred_at=event.get('occurred_at', datetime.utcnow()),
        service=event['service'],
        event_type=event['event_type'],
        actor_id=event.get('actor_id'),
        entity_type=event.get('entity_type'),
        entity_id=event.get('entity_id'),
        severity=event.get('severity', 'info'),
        payload=event['payload'],
        metadata_=event.get('metadata'),
        checksum=_compute_checksum(event.get('payload'))
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit.id

def fetch_audit(db: Session, audit_id: str):
    rec = db.query(AuditLog).filter(AuditLog.id == audit_id).first()
    return audit_to_dict(rec) if rec else None


def list_audits(db: Session,
                service: Optional[str] = None,
                event_type: Optional[str] = None,
                actor_id: Optional[str] = None,
                entity_type: Optional[str] = None,
                entity_id: Optional[str] = None,
                severity: Optional[str] = None,
                from_ts: Optional[datetime] = None,
                to_ts: Optional[datetime] = None,
                page: int = 1,
                size: int = 50) -> Dict[str, Any]:
    q = db.query(AuditLog)
    if service:
        q = q.filter(AuditLog.service == service)
    if event_type:
        q = q.filter(AuditLog.event_type == event_type)
    if actor_id:
        q = q.filter(AuditLog.actor_id == actor_id)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        q = q.filter(AuditLog.entity_id == entity_id)
    if severity:
        q = q.filter(AuditLog.severity == severity)
    if from_ts:
        q = q.filter(AuditLog.occurred_at >= from_ts)
    if to_ts:
        q = q.filter(AuditLog.occurred_at <= to_ts)

    total = q.count()
    q = q.order_by(AuditLog.occurred_at.desc()).offset((page - 1) * size).limit(size)
    items = [audit_to_dict(a) for a in q.all()]
    return {'total': total, 'page': page, 'size': size, 'items': items}
