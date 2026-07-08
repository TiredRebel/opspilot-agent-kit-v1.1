from app import db
from app.main import app
from fastapi.testclient import TestClient


def test_health_ok(monkeypatch):
    monkeypatch.setattr(db, "check_db", lambda: _ok())
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": True}


def test_health_db_down(monkeypatch):
    monkeypatch.setattr(db, "check_db", lambda: _down())
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "db": False, "error": "ConnectionError"}


async def _ok() -> tuple[bool, str | None]:
    return True, None


async def _down() -> tuple[bool, str | None]:
    return False, "ConnectionError"
