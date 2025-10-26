from sqlalchemy import Column, String, TIMESTAMP, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from app.core.database import Base
from sqlalchemy.sql import text

class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "auth_service"}

    audit_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    event_type = Column(String(64), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("auth_service.user.user_id"))
    phone_number = Column(String(32))
    email = Column(String(255))
    ip_address = Column(INET)
    user_agent = Column(Text)
    device_info = Column(JSONB)
    event_data = Column(JSONB)
    severity = Column(String(16))
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    # relationships
    user = relationship("User", back_populates="audits")
