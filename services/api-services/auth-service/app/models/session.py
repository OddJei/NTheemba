from sqlalchemy import Column, String, TIMESTAMP, ForeignKey, Interval
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from app.core.database import Base
from sqlalchemy.sql import text

class UserSession(Base):
    __tablename__ = "user_session"
    __table_args__ = {"schema": "auth_service"}

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("auth_service.user.user_id"), nullable=False)
    jwt_id = Column(String(64), unique=True, nullable=False)
    issued_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    last_activity_at = Column(TIMESTAMP(timezone=True))
    timeout_window = Column(Interval, nullable=False)
    status = Column(String(32), server_default="active")
    device_info = Column(JSONB)
    ip_address = Column(INET)
    user_agent = Column(String)
    meta = Column(JSONB)

    # relationships
    user = relationship("User", back_populates="sessions")
