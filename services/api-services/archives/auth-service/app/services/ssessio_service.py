import datetime
from app.repositories.session_repository import SessionRepository
from app.utils.jwt_utils import create_jwt, decode_jwt
from app.models.session import UserSession

class SessionService:
    def __init__(self, repo: SessionRepository):
        self.repo = repo

    def create_session(self, user_id: str, role: str, timeout_minutes: int = 30) -> UserSession:
        payload = {"user_id": user_id, "role": role}
        token, jti, exp = create_jwt(payload, timeout_minutes)

        session = UserSession(
            user_id=user_id,
            jwt_id=jti,
            expires_at=exp,
            timeout_window=datetime.timedelta(minutes=timeout_minutes),
            status="active"
        )
        self.repo.create(session)
        return session, token

    def validate_session(self, token: str) -> dict | None:
        payload = decode_jwt(token)
        if not payload:
            return None
        session = self.repo.find_by_jwt_id(payload["jti"])
        if not session or session.status != "active":
            return None
        return payload

    def logout(self, jwt_id: str):
        session = self.repo.find_by_jwt_id(jwt_id)
        if session:
            session.status = "terminated"
            self.repo.update(session)
