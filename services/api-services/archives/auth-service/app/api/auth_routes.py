from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.auth_schema import LoginRequest, LoginResponse, RegisterRequest, UserResponse
from app.services.auth_service import AuthService
from app.repositories.user_repository import UserRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.otp_repository import OtpRepository
from app.services.session_service import SessionService
from app.services.otp_service import OtpService

router = APIRouter()

def get_auth_service(db: Session = Depends(get_db)):
    user_repo = UserRepository(db)
    role_repo = RoleRepository(db)
    audit_repo = AuditRepository(db)
    session_repo = SessionRepository(db)
    otp_repo = OtpRepository(db)

    session_service = SessionService(session_repo)
    otp_service = OtpService(otp_repo)

    return AuthService(user_repo, role_repo, audit_repo, session_service, otp_service)

@router.post("/register", response_model=UserResponse)
def register(payload: RegisterRequest, service: AuthService = Depends(get_auth_service), db: Session = Depends(get_db)):
    return service.register(db, payload.name, payload.email, payload.phone, payload.password, payload.role)

@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, service: AuthService = Depends(get_auth_service)):
    result = service.login(payload.email, payload.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": result["token"], "token_type": "bearer"}
