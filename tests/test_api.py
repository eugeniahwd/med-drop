"""Tes API end-to-end. Diperluas di M3 (alur /api/verify)."""

from fastapi.testclient import TestClient

from backend.main import create_app


def test_config_endpoint_reports_active_classifier():
    client = TestClient(create_app())
    r = client.get("/api/config")
    assert r.status_code == 200
    clf = r.json()["classifier"]
    assert clf["backend"] in ("mock", "keras")
    assert clf["is_mock"] == (clf["backend"] == "mock")


def test_frontend_is_served_at_root():
    client = TestClient(create_app())
    r = client.get("/")
    assert r.status_code == 200
    assert "MedDrop" in r.text
