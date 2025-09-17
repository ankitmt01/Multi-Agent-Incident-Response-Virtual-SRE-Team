# backend/app/tests/test_health.py
from fastapi.testclient import TestClient
from app.main import app  # <-- changed from backend.app.main to app.main

def test_health_endpoint():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
