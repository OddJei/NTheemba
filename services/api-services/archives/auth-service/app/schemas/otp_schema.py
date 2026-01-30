from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime

class OtpSendRequest(BaseModel):
    user_id: UUID
    purpose: str
    phone: str | None = None
    email: EmailStr | None = None

class OtpVerifyRequest(BaseModel):
    user_id: UUID
    purpose: str
    code: str

class OtpResponse(BaseModel):
    otp_id: UUID
    expires_at: datetime
