from unittest import mock

import requests

from app.extensions import db
from app.models import Deployment, Incident, Service
from app.seed import seed_demo_data


def test_dashboard_renders_stats(auth_client, post_deployment):
    post_deployment(deployment_status="success")
    post_deployment(deployment_status="failed", build_number=43)
    response = auth_client.get("/dashboard")
    assert response.status_code == 200
    html = response.data.decode()
    assert "Deployment overview" in html
    assert "Success rate" in html
    assert "50.0" in html


def test_chart_data_endpoint(auth_client, post_deployment):
    post_deployment()
    data = auth_client.get("/dashboard/chart-data").get_json()
    assert len(data["trend"]["labels"]) == 14
    assert sum(data["trend"]["success"]) == 1
    assert data["status"]["values"][0] == 1
    assert data["services"]["labels"] == ["demo-app"]


def test_deployment_history_and_filters(auth_client, post_deployment):
    post_deployment(commit_message="fix: searchable change")
    post_deployment(build_number=50, deployment_status="failed")
    assert auth_client.get("/deployments").status_code == 200
    html = auth_client.get("/deployments?q=searchable").data.decode()
    assert "searchable change" in html
    html = auth_client.get("/deployments?status=failed").data.decode()
    assert "#50" in html and "#42" not in html


def test_deployment_detail_page(auth_client, post_deployment):
    dep_id = post_deployment(deployment_status="failed").get_json()["deployment"]["id"]
    response = auth_client.get(f"/deployments/{dep_id}")
    assert response.status_code == 200
    assert b"a1b2c3d4e5f6a7b8c9d0" in response.data
    assert b"Linked incidents" in response.data


def test_deployment_detail_404(auth_client):
    response = auth_client.get("/deployments/12345")
    assert response.status_code == 404
    assert b"Not Found" in response.data


# ---------------- Services CRUD ----------------

def test_service_crud(auth_client):
    response = auth_client.post(
        "/services/new",
        data={
            "name": "orders-api",
            "description": "Orders",
            "environment": "staging",
            "status": "active",
            "repository_url": "https://github.com/example/orders",
            "health_check_url": "http://orders:8080/health",
        },
    )
    assert response.status_code == 302
    service = Service.query.filter_by(name="orders-api").one()
    assert service.environment == "staging"

    assert auth_client.get("/services/").status_code == 200
    assert auth_client.get(f"/services/{service.id}").status_code == 200
    assert auth_client.get(f"/services/{service.id}/edit").status_code == 200

    response = auth_client.post(
        f"/services/{service.id}/edit",
        data={"name": "orders-api", "environment": "production", "status": "inactive"},
    )
    assert response.status_code == 302
    db.session.refresh(service)
    assert service.environment == "production"
    assert service.status == "inactive"

    response = auth_client.post(f"/services/{service.id}/delete")
    assert response.status_code == 302
    assert Service.query.filter_by(name="orders-api").first() is None


def test_service_validation(auth_client):
    response = auth_client.post(
        "/services/new", data={"name": "!", "repository_url": "ftp://x", "environment": "mars"}
    )
    assert response.status_code == 400
    assert Service.query.count() == 0


def test_service_duplicate_name(auth_client):
    auth_client.post("/services/new", data={"name": "dup-svc"})
    response = auth_client.post("/services/new", data={"name": "dup-svc"})
    assert response.status_code == 400
    assert b"already exists" in response.data


def test_service_delete_cascades(auth_client, post_deployment):
    post_deployment(deployment_status="failed")
    service = Service.query.one()
    auth_client.post(f"/services/{service.id}/delete")
    assert Deployment.query.count() == 0
    assert Incident.query.count() == 0


def test_service_health_check_healthy(auth_client, app):
    service = Service(name="demo-app", health_check_url="http://demo-app:8080/health")
    db.session.add(service)
    db.session.commit()
    fake = mock.Mock(status_code=200)
    with mock.patch("app.health.requests.get", return_value=fake):
        response = auth_client.post(f"/services/{service.id}/health-check", follow_redirects=True)
    assert b"HEALTHY" in response.data
    db.session.refresh(service)
    assert service.last_health_status == "healthy"


def test_service_health_check_unhealthy_and_unreachable(auth_client):
    service = Service(name="demo-app", health_check_url="http://demo-app:8080/health")
    db.session.add(service)
    db.session.commit()
    with mock.patch("app.health.requests.get", return_value=mock.Mock(status_code=500)):
        auth_client.post(f"/services/{service.id}/health-check")
    db.session.refresh(service)
    assert service.last_health_status == "unhealthy"
    with mock.patch("app.health.requests.get", side_effect=requests.ConnectionError()):
        auth_client.post(f"/services/{service.id}/health-check")
    db.session.refresh(service)
    assert service.last_health_status == "unreachable"


# ---------------- Incidents CRUD ----------------

def test_incident_crud(auth_client):
    service = Service(name="payments-api")
    db.session.add(service)
    db.session.commit()

    response = auth_client.post(
        "/incidents/new",
        data={"title": "Latency spike", "severity": "critical", "status": "open", "service_id": service.id},
    )
    assert response.status_code == 302
    incident = Incident.query.one()
    assert incident.service_id == service.id

    assert auth_client.get("/incidents/").status_code == 200
    assert auth_client.get(f"/incidents/{incident.id}").status_code == 200
    assert auth_client.get(f"/incidents/{incident.id}/edit").status_code == 200

    response = auth_client.post(
        f"/incidents/{incident.id}/edit",
        data={"title": "Latency spike (p99)", "severity": "high", "status": "investigating", "service_id": service.id},
    )
    assert response.status_code == 302
    db.session.refresh(incident)
    assert incident.title == "Latency spike (p99)"
    assert incident.status == "investigating"
    assert incident.resolved_at is None

    auth_client.post(f"/incidents/{incident.id}/resolve")
    db.session.refresh(incident)
    assert incident.status == "resolved"
    assert incident.resolved_at is not None

    auth_client.post(f"/incidents/{incident.id}/delete")
    assert Incident.query.count() == 0


def test_incident_validation(auth_client):
    response = auth_client.post("/incidents/new", data={"title": "x", "severity": "apocalyptic"})
    assert response.status_code == 400
    response = auth_client.post("/incidents/new", data={"title": "Valid title", "service_id": 999})
    assert response.status_code == 400
    assert Incident.query.count() == 0


def test_incident_filters(auth_client, post_deployment):
    post_deployment(deployment_status="failed")
    assert b"Deployment #42" in auth_client.get("/incidents/?status=open").data
    assert b"Deployment #42" not in auth_client.get("/incidents/?status=resolved").data


# ---------------- Seed data ----------------

def test_seed_demo_data_is_idempotent(app):
    assert seed_demo_data() is True
    services = Service.query.count()
    deployments = Deployment.query.count()
    assert services == 4
    assert deployments > 20
    assert seed_demo_data() is False
    assert Deployment.query.count() == deployments


def test_all_pages_render_with_seed_data(auth_client, app):
    seed_demo_data()
    dep = Deployment.query.first()
    svc = Service.query.first()
    inc = Incident.query.first()
    for url in [
        "/dashboard",
        "/dashboard/chart-data",
        "/deployments",
        "/deployments?page=2",
        f"/deployments/{dep.id}",
        "/services/",
        f"/services/{svc.id}",
        "/services/new",
        "/incidents/",
        f"/incidents/{inc.id}",
        "/incidents/new",
    ]:
        assert auth_client.get(url).status_code == 200, url
