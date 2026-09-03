def test_register_success(client):
    res = client.post(
        "/api/auth/register", json={"email": "new@example.com", "password": "password123"}
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["user"]["email"] == "new@example.com"
    assert data["user"]["role"] == "user"
    assert data["token"]


def test_register_duplicate_email_rejected(client, make_user):
    make_user("dupe@example.com")
    res = client.post(
        "/api/auth/register", json={"email": "dupe@example.com", "password": "password123"}
    )
    assert res.status_code == 400
    assert "already registered" in res.get_json()["error"]


def test_register_weak_password_rejected(client):
    res = client.post(
        "/api/auth/register", json={"email": "weak@example.com", "password": "short"}
    )
    assert res.status_code == 400


def test_register_invalid_email_rejected(client):
    res = client.post(
        "/api/auth/register", json={"email": "not-an-email", "password": "password123"}
    )
    assert res.status_code == 400


def test_login_success(client, make_user):
    make_user("login@example.com", password="password123")
    res = client.post(
        "/api/auth/login", json={"email": "login@example.com", "password": "password123"}
    )
    assert res.status_code == 200
    assert res.get_json()["token"]


def test_login_wrong_password_rejected(client, make_user):
    make_user("login2@example.com", password="password123")
    res = client.post(
        "/api/auth/login", json={"email": "login2@example.com", "password": "wrongpass"}
    )
    assert res.status_code == 400


def test_login_deactivated_account_rejected(client, make_user):
    make_user("disabled@example.com", password="password123", active=False)
    res = client.post(
        "/api/auth/login", json={"email": "disabled@example.com", "password": "password123"}
    )
    assert res.status_code == 400
    assert "deactivated" in res.get_json()["error"]


def test_me_requires_auth(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_me_returns_current_user(client, make_user, auth_header):
    user = make_user("me@example.com")
    res = client.get("/api/auth/me", headers=auth_header(user["token"]))
    assert res.status_code == 200
    assert res.get_json()["user"]["email"] == "me@example.com"


def test_me_rejects_deactivated_users_session_immediately(client, make_user, auth_header):
    """A token issued while active must stop working the moment the account
    is deactivated server-side — not just on the next login."""
    user = make_user("live@example.com")
    ok = client.get("/api/auth/me", headers=auth_header(user["token"]))
    assert ok.status_code == 200

    import backend.app as app_module

    app_module.users_col.update_one({"_id": user["id"]}, {"$set": {"active": False}})

    blocked = client.get("/api/auth/me", headers=auth_header(user["token"]))
    assert blocked.status_code == 401
