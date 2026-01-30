from sqlalchemy import Column, String, Integer, Boolean, TIMESTAMP, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from app.core.database import Base
from sqlalchemy.sql import text

class OtpVerification(Base):
    __tablename__ = "otp_verification"
    __table_args__ = {"schema": "auth_service"}

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("auth_service.user.user_id"))
    phone_number = Column(String(32))
    email = Column(String(255))
    otp_code = Column(String(10), nullable=False)
    purpose = Column(String(32), nullable=False)
    attempts = Column(Integer, server_default="0")
    max_attempts = Column(Integer, server_default="5")
    is_verified = Column(Boolean, server_default=text("false"))
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    verified_at = Column(TIMESTAMP(timezone=True))
    ip_address = Column(INET)
    user_agent = Column(Text)
    session_token = Column(String(255))
    meta = Column(JSONB)

    # relationships
    user = relationship("User", back_populates="otps")
