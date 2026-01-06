def test_docs(client):
    r = client.get("/docs")
    assert r.status_code == 200
