from fastapi.testclient import TestClient

from gqmrmed.main import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "GQMRMed"
