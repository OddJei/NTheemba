import datetime
from app.repositories.otp_repository import OtpRepository
from app.utils.otp_utils import generate_otp
from app.models.otp import OtpVerification

class OtpService:
    def __init__(self, repo: OtpRepository):
        self.repo = repo

    def send_otp(self, user_id: str, purpose: str, phone: str = None, email: str = None) -> OtpVerification:
        code = generate_otp()
        otp = OtpVerification(
            user_id=user_id,
            phone_number=phone,
            email=email,
            otp_code=code,
            purpose=purpose,
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=5)
        )
        return self.repo.create(otp)

    def verify_otp(self, user_id: str, purpose: str, code: str) -> bool:
        otp = self.repo.find_active(user_id, purpose)
        if not otp:
            return False
        if otp.otp_code != code:
            otp.attempts += 1
            self.repo.update(otp)
            return False
        otp.is_verified = True
        self.repo.update(otp)
        return True
