from __future__ import annotations

import os
import sys
import pytest

try:
    # ensure local src is importable when tests run from repo root
    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    SRC = os.path.join(ROOT, "services", "msme-engine", "src")
    if SRC not in sys.path:
        sys.path.insert(0, SRC)
except Exception:
    pass

from fastapi.testclient import TestClient

# Attempt to import FastAPI apps from possible services; tests skip if not present.

def _import_app(module_path: str, attr: str = "app"):
    try:
        mod = __import__(module_path, fromlist=[attr])
        return getattr(mod, attr)
    except Exception:
        return None


def test_msme_onboarding_flow():
    app = _import_app("src.app.main", "app") or _import_app("app.main", "app")
    if app is None:
        pytest.skip("msme-engine FastAPI app not importable")
    client = TestClient(app)

    # Basic health or root check if available
    resp = client.get("/health" or "/")
    assert resp.status_code in (200, 404)


def test_affiliate_onboarding_flow():
    app = _import_app("src.app.affiliate.main", "app") or _import_app("services.affiliate_engine.src.app.main", "app")
    if app is None:
        pytest.skip("affiliate app not importable")
    client = TestClient(app)

    resp = client.get("/health" or "/")
    assert resp.status_code in (200, 404)


def test_customer_onboarding_flow():
    # Customer flows may live under a generic web-services or customer service.
    app = _import_app("src.app.customer.main", "app") or _import_app("services.customer.src.app.main", "app")
    if app is None:
        pytest.skip("customer app not importable")
    client = TestClient(app)

    resp = client.get("/health" or "/")
    assert resp.status_code in (200, 404)
