from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_uses_standard_response_envelope() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == {"status": "UP", "service": "meydanai-api"}
    assert body["timestamp"]


def test_unknown_route_uses_problem_details() -> None:
    response = client.get("/api/v1/unknown")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["errorCode"] == "RESOURCE_NOT_FOUND"
    assert body["status"] == 404
    assert "traceback" not in body


def test_cors_preflight_allows_configured_frontend() -> None:
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
