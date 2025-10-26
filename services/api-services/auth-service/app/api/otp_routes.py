from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.otp_schema import OtpSendRequest, OtpVerifyRequest, OtpResponse
from app.services.otp_service import OtpService
from app.repositories.otp_repository import OtpRepository

router = APIRouter()

def get_otp_service(db: Session = Depends(get_db)):
    return OtpService(OtpRepository(db))

@router.post("/send", response_model=OtpResponse)
def send_otp(payload: OtpSendRequest, service: OtpService = Depends(get_otp_service)):
    otp = service.send_otp(payload.user_id, payload.purpose, phone=payload.phone, email=payload.email)
    return {"otp_id": str(otp.id), "expires_at": otp.expires_at}

@router.post("/verify")
def verify_otp(payload: OtpVerifyRequest, service: OtpService = Depends(get_otp_service)):
    success = service.verify_otp(payload.user_id, payload.purpose, payload.code)
    return {"verified": success}
