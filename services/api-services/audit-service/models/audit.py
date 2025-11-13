from sqlalchemy import Column, String, DateTime, Boolean, Enum, JSON, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
import uuid
from datetime import datetime
from core.database import Base

from sqlalchemy import func

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    # Table will be created in the service schema provided by core.database (SERVICE_SCHEMA)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    occurred_at = Column(DateTime(timezone=True), default=func.now(), index=True)
    service = Column(String(128), nullable=False, index=True)
    event_type = Column(String(128), nullable=False, index=True)
    actor_id = Column(String(36), nullable=True, index=True)
    entity_type = Column(String(128), nullable=True, index=True)
    entity_id = Column(String(36), nullable=True, index=True)
    severity = Column(String(16), nullable=False, default='info')
    payload = Column(JSON, nullable=False)
    # 'metadata' is a reserved attribute on declarative Base; use attribute name 'metadata_'
    # but map it to DB column 'metadata' so downstream code and queries keep the column name.
    metadata_ = Column('metadata', JSON, nullable=True)
    checksum = Column(String(128), nullable=True)
    archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
