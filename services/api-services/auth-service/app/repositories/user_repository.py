from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from app.models.user import User

class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    # CREATE
    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    # READ
    def get_by_id(self, user_id: str) -> User | None:
        return self.db.get(User, user_id)

    def find_by_email(self, email: str) -> User | None:
        return self.db.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()

    def find_by_phone(self, phone: str) -> User | None:
        return self.db.execute(
            select(User).where(User.phone_number == phone)
        ).scalar_one_or_none()

    def list_all(self) -> list[User]:
        return self.db.execute(select(User)).scalars().all()

    # UPDATE
    def update(self, user: User) -> User:
        self.db.commit()
        self.db.refresh(user)
        return user

    # DELETE
    def delete(self, user: User):
        self.db.delete(user)
        self.db.commit()

    def delete_by_id(self, user_id: str):
        self.db.execute(delete(User).where(User.user_id == user_id))
        self.db.commit()
