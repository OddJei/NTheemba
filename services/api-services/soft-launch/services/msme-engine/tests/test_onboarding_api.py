from __future__ import annotations

import os
import sys
import pytest

try:
    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    SRC = os.path.join(ROOT, "services", "msme-engine", "src")
    if SRC not in sys.path:
        sys.path.insert(0, SRC)
except Exception:
    pass

# Force tests to use an in-memory SQLite DB to avoid connecting to real Postgres during CI/local runs
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from fastapi.testclient import TestClient


def _import_app(module_path: str, attr: str = "app"):
    try:
        mod = __import__(module_path, fromlist=[attr])
        return getattr(mod, attr)
    except Exception:
        return None


app = _import_app("src.app.main", "app") or _import_app("app.main", "app")
if app is None:
    # Fallback: load module directly from file path (robust on local dev)
    import importlib.util

    # Try direct path relative to this test file: ../src/app/main.py
    candidate = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "app", "main.py"))
    if os.path.exists(candidate):
        spec = importlib.util.spec_from_file_location("msme_app_main", candidate)
        mod = importlib.util.module_from_spec(spec)
        # Ensure msme-engine root is on sys.path so `src.*` imports resolve
        msme_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if msme_root not in sys.path:
            sys.path.insert(0, msme_root)
        spec.loader.exec_module(mod)  # type: ignore
        app = getattr(mod, "app", None)

    if app is None:
        raise RuntimeError("msme app not importable for tests")


def test_msme_onboard_endpoint():
    client = TestClient(app)
    payload = {
        "profile": {
            "fullName": "Test Owner",
            "email": "owner+msme@example.com",
            "phone": "+260700000001",
            "location": "Lusaka",
        },
        "business": {
            "businessName": "Test Business Ltd",
            "businessType": "Retail",
            "description": "Test description",
            "yearsInBusiness": "1-3",
        },
        "products": [
            {"name": "Soap", "category": "Beauty", "price": "50", "initialStock": "100"}
        ],
    }

    r = client.post("/msme/onboard", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert "business" in body and "user" in body and "msme_code" in body


def test_affiliate_onboard_endpoint():
    client = TestClient(app)
    payload = {
        "profile": {"fullName": "Affiliate One", "email": "aff+1@example.com", "phone": "+260700000002", "location": "Lusaka"},
        "preferences": {"categories": ["beauty", "fashion"], "commissionPreference": "balanced", "bio": "Test affiliate"},
    }

    r = client.post("/affiliate/onboard", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert "user" in body and "affiliate_id" in body
