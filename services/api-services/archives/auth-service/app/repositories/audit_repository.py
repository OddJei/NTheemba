from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from app.models.audit import AuditLog

class AuditRepository:
    def __init__(self, db: Session):
        self.db = db

    # CREATE
    def log_event(self, audit: AuditLog) -> AuditLog:
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(audit)
        return audit

    # READ
    def get_by_id(self, audit_id: str) -> AuditLog | None:
        return self.db.get(AuditLog, audit_id)

    def list_by_user(self, user_id: str) -> list[AuditLog]:
        return self.db.execute(
            select(AuditLog).where(AuditLog.user_id == user_id)
        ).scalars().all()

    def list_all(self, limit: int = 100) -> list[AuditLog]:
        return self.db.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        ).scalars().all()

    # UPDATE
    def update(self, audit: AuditLog) -> AuditLog:
        self.db.commit()
        self.db.refresh(audit)
        return audit

    # DELETE
    def delete(self, audit: AuditLog):
        self.db.delete(audit)
        self.db.commit()

    def delete_by_id(self, audit_id: str):
        self.db.execute(delete(AuditLog).where(AuditLog.audit_id == audit_id))
        self.db.commit()
