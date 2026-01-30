from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from app.models.role import Role

class RoleRepository:
    def __init__(self, db: Session):
        self.db = db

    # CREATE
    def create(self, role: Role) -> Role:
        self.db.add(role)
        self.db.commit()
        self.db.refresh(role)
        return role

    # READ
    def get_by_id(self, role_id: str) -> Role | None:
        return self.db.get(Role, role_id)

    def find_by_name(self, name: str) -> Role | None:
        return self.db.execute(
            select(Role).where(Role.name == name)
        ).scalar_one_or_none()

    def list_all(self) -> list[Role]:
        return self.db.execute(select(Role)).scalars().all()

    # UPDATE
    def update(self, role: Role) -> Role:
        self.db.commit()
        self.db.refresh(role)
        return role

    # DELETE
    def delete(self, role: Role):
        self.db.delete(role)
        self.db.commit()

    def delete_by_id(self, role_id: str):
        self.db.execute(delete(Role).where(Role.role_id == role_id))
        self.db.commit()
