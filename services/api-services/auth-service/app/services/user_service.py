from app.repositories.user_repository import UserRepository
from app.utils.crypto_utils import hash_password, verify_password
from app.models.user import User

class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    def register_user(self, db, name: str, email: str, phone: str, password: str, role_id: str) -> User:
        hashed_pw = hash_password(password)
        user = User(
            name=name,
            email=email,
            phone_number=phone,
            password_hash=hashed_pw,
            role_id=role_id
        )
        return self.repo.create(user)

    def get_user_by_email(self, email: str) -> User | None:
        return self.repo.find_by_email(email)

    def get_user_by_phone(self, phone: str) -> User | None:
        return self.repo.find_by_phone(phone)

    def update_password(self, user: User, new_password: str) -> User:
        user.password_hash = hash_password(new_password)
        return self.repo.update(user)

    def verify_password(self, user: User, password: str) -> bool:
        return verify_password(password, user.password_hash)

    def deactivate_user(self, user: User):
        user.status = "inactive"
        return self.repo.update(user)
