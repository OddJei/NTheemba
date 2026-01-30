from fastapi import APIRouter, Depends, HTTPException
from app.schemas.session_schema import SessionValidateRequest, SessionValidateResponse
from app.services.session_service import SessionService
from app.repositories.session_repository import SessionRepository
from app.core.database import get_db
from sqlalchemy.orm import Session

router = APIRouter()

def get_session_service(db: Session = Depends(get_db)):
    return SessionService(SessionRepository(db))

@router.post("/validate", response_model=SessionValidateResponse)
def validate_session(payload: SessionValidateRequest, service: SessionService = Depends(get_session_service)):
    payload_data = service.validate_session(payload.token)
    if not payload_data:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return {"valid": True, "claims": payload_data}

@router.post("/logout")
def logout(jwt_id: str, service: SessionService = Depends(get_session_service)):
    service.logout(jwt_id)
    return {"status": "logged_out"}
