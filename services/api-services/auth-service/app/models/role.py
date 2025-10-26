from sqlalchemy import Column, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base

class Role(Base):
    __tablename__ = "role"
    __table_args__ = {"schema": "auth_service"}

    role_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name = Column(String(32), unique=True, nullable=False)
    description = Column(String(255))
    permissions = Column(JSONB, nullable=False, server_default="{}")
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    # relationships
    users = relationship("User", back_populates="role")
