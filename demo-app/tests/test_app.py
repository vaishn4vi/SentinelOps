import pytest


def test_index_returns_service_info(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.get_json()
    assert data["service"] == "sentinelops-demo-app"
    assert "/health" in data["endpoints"]


def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert data["uptime_seconds"] >= 0


def test_version_uses_environment(client, monkeypatch):
    monkeypatch.setenv("APP_VERSION", "2.4.1")
    monkeypatch.setenv("BUILD_NUMBER", "57")
    monkeypatch.setenv("COMMIT_ID", "abc1234")
    data = client.get("/version").get_json()
    assert data["version"] == "2.4.1"
    assert data["build_number"] == "57"
    assert data["commit_id"] == "abc1234"


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "on"])
def test_break_mode_fails_health_check(client, monkeypatch, value):
    monkeypatch.setenv("BREAK", value)
    response = client.get("/health")
    assert response.status_code == 500
    assert response.get_json()["status"] == "unhealthy"


def test_break_mode_fails_index(client, monkeypatch):
    monkeypatch.setenv("BREAK", "true")
    assert client.get("/").status_code == 500


def test_version_still_available_in_break_mode(client, monkeypatch):
    monkeypatch.setenv("BREAK", "true")
    assert client.get("/version").status_code == 200


@pytest.mark.parametrize("value", ["false", "0", "no", ""])
def test_non_truthy_break_values_stay_healthy(client, monkeypatch, value):
    monkeypatch.setenv("BREAK", value)
    assert client.get("/health").status_code == 200


def test_unknown_route_returns_json_404(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.get_json()["status"] == "error"


def test_wrong_method_returns_405(client):
    assert client.post("/health").status_code == 405
