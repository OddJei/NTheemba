from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from app.models.session import UserSession

class SessionRepository:
    def __init__(self, db: Session):
        self.db = db

    # CREATE
    def create(self, session: UserSession) -> UserSession:
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    # READ
    def get_by_id(self, session_id: str) -> UserSession | None:
        return self.db.get(UserSession, session_id)

    def find_by_jwt_id(self, jwt_id: str) -> UserSession | None:
        return self.db.execute(
            select(UserSession).where(UserSession.jwt_id == jwt_id)
        ).scalar_one_or_none()

    def find_by_user(self, user_id: str) -> list[UserSession]:
        return self.db.execute(
            select(UserSession).where(UserSession.user_id == user_id)
        ).scalars().all()

    # UPDATE
    def update(self, session: UserSession) -> UserSession:
        self.db.commit()
        self.db.refresh(session)
        return session

    def update_last_activity(self, session: UserSession) -> UserSession:
        self.db.commit()
        self.db.refresh(session)
        return session

    # DELETE
    def delete(self, session: UserSession):
        self.db.delete(session)
        self.db.commit()

    def delete_by_jwt_id(self, jwt_id: str):
        self.db.execute(delete(UserSession).where(UserSession.jwt_id == jwt_id))
        self.db.commit()

    def delete_expired_sessions(self) -> None:
        sessions = self.db.execute(
            select(UserSession).where(UserSession.expires_at < func.now())
        ).scalars().all()
        for session in sessions:
            self.db.delete(session)
        self.db.commit()
    
    