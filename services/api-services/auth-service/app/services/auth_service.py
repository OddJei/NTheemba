from app.repositories.user_repository import UserRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.audit_repository import AuditRepository
from app.services.user_service import UserService
from app.services.session_service import SessionService
from app.services.otp_service import OtpService
from app.models.audit import AuditLog

class AuthService:
    def __init__(self, user_repo: UserRepository, role_repo: RoleRepository,
                 audit_repo: AuditRepository, session_service: SessionService,
                 otp_service: OtpService):
        self.user_service = UserService(user_repo)
        self.role_repo = role_repo
        self.audit_repo = audit_repo
        self.session_service = session_service
        self.otp_service = otp_service

    def register(self, db, name: str, email: str, phone: str, password: str, role_name: str):
        role = self.role_repo.find_by_name(role_name)
        user = self.user_service.register_user(db, name, email, phone, password, role.role_id)
        self.audit_repo.log_event(AuditLog(event_type="REGISTER", user_id=user.user_id, event_data={"email": email}))
        return user

    def login(self, email: str, password: str):
        user = self.user_service.get_user_by_email(email)
        if not user or not self.user_service.verify_password(user, password):
            self.audit_repo.log_event(AuditLog(event_type="LOGIN_FAILED", email=email))
            return None
        session, token = self.session_service.create_session(user.user_id, user.role.name)
        self.audit_repo.log_event(AuditLog(event_type="LOGIN_SUCCESS", user_id=user.user_id))
        return {"user": user, "token": token}

    def logout(self, jwt_id: str, user_id: str):
        self.session_service.logout(jwt_id)
        self.audit_repo.log_event(AuditLog(event_type="LOGOUT", user_id=user_id))

    def send_login_otp(self, user_id: str, phone: str):
        return self.otp_service.send_otp(user_id, "login", phone=phone)

    def verify_login_otp(self, user_id: str, code: str):
        return self.otp_service.verify_otp(user_id, "login", code)
