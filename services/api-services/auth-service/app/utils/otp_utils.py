from datetime import datetime, timedelta
import random
import pyotp

class OTPManager:
    def __init__(self, secret=None):
        self.secret = secret or pyotp.random_base32()
        self.totp = pyotp.TOTP(self.secret)

    def generate_otp(self):
        return self.totp.now()

    def validate_otp(self, otp):
        return self.totp.verify(otp)

    def get_secret(self):
        return self.secret

    def get_expiration_time(self):
        return datetime.now() + timedelta(minutes=5)  # OTP valid for 5 minutes

# Example usage:
# otp_manager = OTPManager()
# otp = otp_manager.generate_otp()
# print(f"Generated OTP: {otp}")
# print(f"Is OTP valid? {otp_manager.validate_otp(otp)}")