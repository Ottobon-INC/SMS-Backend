from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import app.main as main_module
from app.main import app


def test_health_endpoint() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_endpoint_does_not_expose_database_url() -> None:
    response = TestClient(app).get("/health")
    assert "DATABASE_URL" not in response.text
    assert "postgresql://" not in response.text


def test_lifespan_runs_database_check_and_disposes_engine(monkeypatch: MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_check_database_connection() -> None:
        calls.append("check")

    def fake_dispose_engine() -> None:
        calls.append("dispose")

    monkeypatch.setattr(main_module, "check_database_connection", fake_check_database_connection)
    monkeypatch.setattr(main_module, "dispose_engine", fake_dispose_engine)

    with TestClient(app):
        pass

    assert calls == ["check", "dispose"]
