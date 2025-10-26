from pydantic import BaseModel, EmailStr
from uuid import UUID

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str
    password: str
    role_id: UUID

class UserRead(BaseModel):
    user_id: UUID
    name: str
    email: EmailStr
    phone_number: str
    role_id: UUID
    status: str

    class Config:
        orm_mode = True
