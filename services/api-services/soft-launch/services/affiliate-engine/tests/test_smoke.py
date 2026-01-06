from __future__ import annotations

def test_health_smoke(client) -> None:
    resp = client.get("/docs")
    assert resp.status_code in (200, 302)
