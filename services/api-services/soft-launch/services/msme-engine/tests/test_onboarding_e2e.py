import asyncio
import os
import time
from httpx import AsyncClient
import pytest

from src.app.main import app

BASE_URL = "http://test"

@pytest.mark.asyncio
async def test_user_and_business_onboarding_e2e():
    # Register user
    async with AsyncClient(app=app, base_url=BASE_URL) as ac:
        reg = {
            "username": "e2e_user",
            "email": "e2e@example.com",
            "phone": "+260123456789",
            "password": "password123",
            "role": "msme",
        }
        r = await ac.post("/auth/register", json=reg)
        assert r.status_code == 201
        token_pair = None

        # Login
        login = {"identifier": "e2e_user", "password": "password123"}
        r2 = await ac.post("/auth/login", json=login)
        assert r2.status_code == 200
        token_pair = r2.json()
        assert "access_token" in token_pair and "refresh_token" in token_pair

        access = token_pair["access_token"]

        # Register business using owner_user_id
        headers = {"Authorization": f"Bearer {access}"}
        biz_payload = {
            "name": "E2E Business",
            "owner_user_id": None,
            "owner": {"username": "biz_owner", "email": "owner@example.com", "phone": "+260987654321", "password": "ownerpass"},
            "location": "Lusaka",
        }
        r3 = await ac.post("/business/register", json=biz_payload, headers=headers)
        assert r3.status_code in (200, 201)
