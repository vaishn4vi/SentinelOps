import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app  # noqa: E402
from app.extensions import db as _db  # noqa: E402
from app.models import User  # noqa: E402

API_KEY = "test-api-key"


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user(app):
    u = User(username="alice", email="alice@example.com")
    u.set_password("Secret123")
    _db.session.add(u)
    _db.session.commit()
    return u


@pytest.fixture
def auth_client(client, user):
    response = client.post("/auth/login", data={"username": "alice", "password": "Secret123"})
    assert response.status_code == 302
    return client


@pytest.fixture
def api_headers():
    return {"X-API-Key": API_KEY, "Content-Type": "application/json"}


@pytest.fixture
def deployment_payload():
    return {
        "commit_id": "a1b2c3d4e5f6a7b8c9d0",
        "commit_author": "Priya Sharma",
        "commit_message": "feat: add health endpoint",
        "build_number": 42,
        "image_tag": "sentinelops/demo-app:42",
        "deployment_status": "success",
        "service_name": "demo-app",
    }


@pytest.fixture
def post_deployment(client, api_headers, deployment_payload):
    def _post(**overrides):
        payload = {**deployment_payload, **overrides}
        return client.post("/api/deployments", json=payload, headers=api_headers)

    return _post
