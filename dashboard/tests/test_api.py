from app.extensions import db
from app.models import Deployment, Incident, Service


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "database": "up"}


def test_post_deployment_requires_api_key(client, deployment_payload):
    response = client.post("/api/deployments", json=deployment_payload)
    assert response.status_code == 401


def test_post_deployment_rejects_wrong_key(client, deployment_payload):
    response = client.post("/api/deployments", json=deployment_payload, headers={"X-API-Key": "nope"})
    assert response.status_code == 401


def test_post_deployment_accepts_bearer_token(client, deployment_payload):
    response = client.post(
        "/api/deployments", json=deployment_payload, headers={"Authorization": "Bearer test-api-key"}
    )
    assert response.status_code == 201


def test_post_deployment_success_creates_records(post_deployment):
    response = post_deployment()
    assert response.status_code == 201
    body = response.get_json()
    assert body["service_created"] is True
    assert body["incident_id"] is None
    assert body["deployment"]["deployment_status"] == "success"
    assert body["deployment"]["build_number"] == 42
    assert response.headers["Location"].endswith(f"/api/deployments/{body['deployment']['id']}")
    assert Service.query.filter_by(name="demo-app").count() == 1
    assert Deployment.query.count() == 1


def test_post_deployment_reuses_existing_service(post_deployment):
    post_deployment()
    response = post_deployment(build_number=43)
    assert response.get_json()["service_created"] is False
    assert Service.query.count() == 1


def test_failed_deployment_opens_incident_and_degrades_service(post_deployment):
    response = post_deployment(deployment_status="failed")
    body = response.get_json()
    assert response.status_code == 201
    assert body["incident_id"] is not None
    incident = db.session.get(Incident, body["incident_id"])
    assert incident.auto_generated is True
    assert incident.severity == "high"
    assert Service.query.filter_by(name="demo-app").one().status == "degraded"


def test_successful_deploy_heals_degraded_service(post_deployment):
    post_deployment(deployment_status="failed")
    post_deployment(deployment_status="success", build_number=43)
    assert Service.query.filter_by(name="demo-app").one().status == "active"


def test_status_aliases_are_normalised(post_deployment):
    response = post_deployment(deployment_status="ROLLBACK")
    assert response.get_json()["deployment"]["deployment_status"] == "rolled_back"


def test_post_deployment_validation_errors(post_deployment):
    response = post_deployment(build_number="abc", deployment_status="exploded", commit_id="")
    assert response.status_code == 422
    fields = response.get_json()["fields"]
    assert "build_number" in fields
    assert "deployment_status" in fields
    assert "commit_id" in fields


def test_post_deployment_missing_fields(client, api_headers):
    response = client.post("/api/deployments", json={"commit_id": "abc123"}, headers=api_headers)
    assert response.status_code == 422
    fields = response.get_json()["fields"]
    for name in ("commit_author", "build_number", "image_tag", "deployment_status", "service_name"):
        assert name in fields


def test_post_deployment_invalid_json(client, api_headers):
    response = client.post("/api/deployments", data="not-json", headers=api_headers)
    assert response.status_code == 400


def test_post_deployment_rejects_non_object_body(client, api_headers):
    response = client.post("/api/deployments", json=[1, 2, 3], headers=api_headers)
    assert response.status_code == 422


def test_get_deployments_lists_and_filters(client, api_headers, post_deployment):
    post_deployment(build_number=1)
    post_deployment(build_number=2, deployment_status="failed")
    post_deployment(build_number=3, service_name="payments-api")

    data = client.get("/api/deployments", headers=api_headers).get_json()
    assert data["total"] == 3
    assert len(data["deployments"]) == 3

    failed = client.get("/api/deployments?status=failed", headers=api_headers).get_json()
    assert failed["total"] == 1
    assert failed["deployments"][0]["build_number"] == 2

    payments = client.get("/api/deployments?service_name=payments-api", headers=api_headers).get_json()
    assert payments["total"] == 1

    paged = client.get("/api/deployments?limit=2&offset=0", headers=api_headers).get_json()
    assert len(paged["deployments"]) == 2


def test_get_deployments_bad_params(client, api_headers):
    assert client.get("/api/deployments?limit=x", headers=api_headers).status_code == 400
    assert client.get("/api/deployments?status=weird", headers=api_headers).status_code == 400


def test_get_deployments_requires_auth(client):
    assert client.get("/api/deployments").status_code == 401


def test_get_single_deployment(client, api_headers, post_deployment):
    dep_id = post_deployment(deployment_status="failed").get_json()["deployment"]["id"]
    data = client.get(f"/api/deployments/{dep_id}", headers=api_headers).get_json()
    assert data["id"] == dep_id
    assert len(data["incidents"]) == 1
    assert client.get("/api/deployments/9999", headers=api_headers).status_code == 404


def test_stats_endpoint(client, api_headers, post_deployment):
    post_deployment(build_number=1, deployment_status="success")
    post_deployment(build_number=2, deployment_status="success")
    post_deployment(build_number=3, deployment_status="success")
    post_deployment(build_number=4, deployment_status="failed")
    post_deployment(build_number=5, deployment_status="rolled_back")

    stats = client.get("/api/stats", headers=api_headers).get_json()
    assert stats["total_deployments"] == 5
    assert stats["successful_deployments"] == 3
    assert stats["failed_deployments"] == 1
    assert stats["rollback_count"] == 1
    assert stats["success_percentage"] == 60.0
    assert stats["total_services"] == 1
    assert stats["open_incidents"] == 2
    assert stats["last_deployment"]["build_number"] in {1, 2, 3, 4, 5}


def test_stats_empty_database(client, api_headers):
    stats = client.get("/api/stats", headers=api_headers).get_json()
    assert stats["total_deployments"] == 0
    assert stats["success_percentage"] == 0.0


def test_stats_accessible_with_browser_session(auth_client):
    assert auth_client.get("/api/stats").status_code == 200


def test_api_unknown_route_returns_json(client):
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert response.is_json


def test_api_locked_when_key_not_configured(app, client, deployment_payload):
    app.config["SENTINELOPS_API_KEY"] = ""
    response = client.post("/api/deployments", json=deployment_payload, headers={"X-API-Key": "anything"})
    assert response.status_code == 503
