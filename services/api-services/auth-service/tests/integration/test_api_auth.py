import pytest
from fastapi.testclient import TestClient
from ntheemba_auth.main import app

client = TestClient(app)

def test_login_success():
    response = client.post("/api/v1/auth/login", json={"username": "testuser", "password": "testpassword"})
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_login_failure():
    response = client.post("/api/v1/auth/login", json={"username": "testuser", "password": "wrongpassword"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}

def test_register_success():
    response = client.post("/api/v1/auth/register", json={"username": "newuser", "password": "newpassword"})
    assert response.status_code == 201
    assert response.json() == {"message": "User created successfully"}

def test_register_failure():
    response = client.post("/api/v1/auth/register", json={"username": "", "password": "newpassword"})
    assert response.status_code == 400
    assert response.json() == {"detail": "Username must not be empty"}