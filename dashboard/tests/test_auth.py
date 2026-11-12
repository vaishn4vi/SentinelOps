from app.models import User


def test_root_redirects_to_login_when_anonymous(client):
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_login_page_renders(client):
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert b"Sign in" in response.data


def test_register_creates_user(client, app):
    response = client.post(
        "/auth/register",
        data={
            "username": "bob",
            "email": "bob@example.com",
            "password": "Passw0rd!",
            "confirm_password": "Passw0rd!",
        },
    )
    assert response.status_code == 302
    user = User.query.filter_by(username="bob").first()
    assert user is not None
    assert user.password_hash != "Passw0rd!"
    assert user.check_password("Passw0rd!")


def test_register_rejects_bad_input(client):
    response = client.post(
        "/auth/register",
        data={"username": "x", "email": "nope", "password": "short", "confirm_password": "diff"},
    )
    assert response.status_code == 400
    assert b"Enter a valid email address" in response.data


def test_register_rejects_duplicate_username(client, user):
    response = client.post(
        "/auth/register",
        data={
            "username": "alice",
            "email": "other@example.com",
            "password": "Passw0rd1",
            "confirm_password": "Passw0rd1",
        },
    )
    assert response.status_code == 400
    assert b"already taken" in response.data


def test_login_with_valid_credentials(client, user):
    response = client.post("/auth/login", data={"username": "alice", "password": "Secret123"})
    assert response.status_code == 302
    assert client.get("/dashboard").status_code == 200


def test_login_with_email(client, user):
    response = client.post("/auth/login", data={"username": "ALICE@example.com", "password": "Secret123"})
    assert response.status_code == 302


def test_login_with_invalid_password(client, user):
    response = client.post("/auth/login", data={"username": "alice", "password": "wrong"})
    assert response.status_code == 401
    assert b"Invalid username" in response.data


def test_login_ignores_external_next(client, user):
    response = client.post(
        "/auth/login?next=https://evil.example.com",
        data={"username": "alice", "password": "Secret123"},
    )
    assert response.headers["Location"].endswith("/dashboard")


def test_logout(auth_client):
    response = auth_client.post("/auth/logout")
    assert response.status_code == 302
    assert auth_client.get("/dashboard").status_code == 302
