from sqlalchemy import Column, String, Boolean, Integer, TIMESTAMP, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base

class User(Base):
    __tablename__ = "user"
    __table_args__ = {"schema": "auth_service"}

    user_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    phone_number = Column(String(32), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    email_verified_at = Column(TIMESTAMP(timezone=True))
    name = Column(String(128))
    password_hash = Column(String(255))
    passcode_hash = Column(String(255))
    passcode_expires_at = Column(TIMESTAMP(timezone=True))
    requires_passcode = Column(Boolean, server_default=text("false"))
    role_id = Column(UUID(as_uuid=True), ForeignKey("auth_service.role.role_id"), nullable=False)
    status = Column(String(32), server_default="active")
    failed_login_attempts = Column(Integer, server_default="0")
    last_login_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    meta = Column(JSONB)

    # relationships
    role = relationship("Role", back_populates="users")
    sessions = relationship("UserSession", back_populates="user")
    otps = relationship("OtpVerification", back_populates="user")
    audits = relationship("AuditLog", back_populates="user")
