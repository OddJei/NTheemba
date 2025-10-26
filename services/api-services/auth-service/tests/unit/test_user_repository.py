import pytest
from ntheemba_auth.repositories.user_repository import UserRepository
from ntheemba_auth.models.user import User

@pytest.fixture
def user_repository():
    return UserRepository()

def test_create_user(user_repository):
    user_data = {
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "securepassword"
    }
    user = user_repository.create_user(user_data)
    assert user.username == user_data["username"]
    assert user.email == user_data["email"]

def test_get_user_by_id(user_repository):
    user_data = {
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "securepassword"
    }
    user = user_repository.create_user(user_data)
    fetched_user = user_repository.get_user_by_id(user.id)
    assert fetched_user.id == user.id

def test_update_user(user_repository):
    user_data = {
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "securepassword"
    }
    user = user_repository.create_user(user_data)
    updated_data = {
        "username": "updateduser",
        "email": "updateduser@example.com"
    }
    updated_user = user_repository.update_user(user.id, updated_data)
    assert updated_user.username == updated_data["username"]
    assert updated_user.email == updated_data["email"]

def test_delete_user(user_repository):
    user_data = {
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "securepassword"
    }
    user = user_repository.create_user(user_data)
    user_repository.delete_user(user.id)
    fetched_user = user_repository.get_user_by_id(user.id)
    assert fetched_user is None