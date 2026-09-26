"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ntheemba.config import Settings
from ntheemba.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        app_name="Ntheemba Test",
        environment="test",
        version="0.1.0-test",
        api_prefix="/api/v1",
        docs_enabled=False,
        gateway_shared_secret=None,
        redis_url=None,
    )


@pytest.fixture
def app(test_settings: Settings) -> FastAPI:
    return create_app(test_settings)


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
