from sqlalchemy.orm import Session
from sqlalchemy import func, select, delete
from app.models.otp import OtpVerification

class OtpRepository:
    def __init__(self, db: Session):
        self.db = db

    # CREATE
    def create(self, otp: OtpVerification) -> OtpVerification:
        self.db.add(otp)
        self.db.commit()
        self.db.refresh(otp)
        return otp

    # READ
    def get_by_id(self, otp_id: str) -> OtpVerification | None:
        return self.db.get(OtpVerification, otp_id)

    def find_active(self, user_id: str, purpose: str) -> OtpVerification | None:
        return self.db.execute(
            select(OtpVerification)
            .where(OtpVerification.user_id == user_id)
            .where(OtpVerification.purpose == purpose)
            .where(OtpVerification.is_verified == False)
        ).scalar_one_or_none()

    def list_by_user(self, user_id: str) -> list[OtpVerification]:
        return self.db.execute(
            select(OtpVerification).where(OtpVerification.user_id == user_id)
        ).scalars().all()

    # UPDATE
    def update(self, otp: OtpVerification) -> OtpVerification:
        self.db.commit()
        self.db.refresh(otp)
        return otp

    def mark_verified(self, otp: OtpVerification) -> OtpVerification:
        otp.is_verified = True
        self.db.commit()
        self.db.refresh(otp)
        return otp

    # DELETE
    def delete(self, otp: OtpVerification):
        self.db.delete(otp)
        self.db.commit()

    def delete_by_id(self, otp_id: str):
        self.db.execute(delete(OtpVerification).where(OtpVerification.id == otp_id))
        self.db.commit()

    def delete_expired_otps(self) -> None:
        otps = self.db.execute(
            select(OtpVerification).where(OtpVerification.expires_at < func.now())
        ).scalars().all()
        for otp in otps:
            self.db.delete(otp)
        self.db.commit()

    def delete_by_user_id(self, user_id: str) -> None:
        otps = self.db.execute(
            select(OtpVerification).where(OtpVerification.user_id == user_id)
        ).scalars().all()
        for otp in otps:
            self.db.delete(otp)
        self.db.commit()
    