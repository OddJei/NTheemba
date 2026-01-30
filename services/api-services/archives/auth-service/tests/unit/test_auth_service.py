import pytest
from ntheemba_auth.services.auth_service import AuthService
from ntheemba_auth.repositories.user_repository import UserRepository
from ntheemba_auth.models.user import User

@pytest.fixture
def user_repository():
    return UserRepository()

@pytest.fixture
def auth_service(user_repository):
    return AuthService(user_repository)

def test_register_user(auth_service):
    user_data = {
        "username": "testuser",
        "password": "securepassword",
        "email": "testuser@example.com"
    }
    user = auth_service.register_user(user_data)
    assert user.username == user_data["username"]
    assert user.email == user_data["email"]

def test_login_user(auth_service):
    user_data = {
        "username": "testuser",
        "password": "securepassword"
    }
    auth_service.register_user(user_data)  # Ensure the user is registered
    token = auth_service.login_user(user_data["username"], user_data["password"])
    assert token is not None

def test_login_user_invalid_credentials(auth_service):
    user_data = {
        "username": "testuser",
        "password": "wrongpassword"
    }
    with pytest.raises(ValueError, match="Invalid credentials"):
        auth_service.login_user(user_data["username"], user_data["password"])