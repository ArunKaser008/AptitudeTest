from app.main import app, health


def test_health_endpoint_contract() -> None:
    assert health() == {"status": "ok"}
    assert "/health" in app.openapi()["paths"]
