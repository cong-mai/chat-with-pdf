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


def test_register_failure_returns_generic_error_and_logs_exception(client, monkeypatch, caplog):
    """A non-duplicate-key failure (e.g. a Mongo connectivity error) must not be
    mislabeled as 'already registered' — it should log and return a generic 500."""
    import backend.app as app_module

    def _boom(*args, **kwargs):
        raise RuntimeError("distinct-marker-register789")

    monkeypatch.setattr(app_module.users_col, "insert_one", _boom)

    with caplog.at_level("ERROR"):
        res = client.post(
            "/api/auth/register", json={"email": "boom@example.com", "password": "password123"}
        )

    assert res.status_code == 500
    assert "already registered" not in res.get_json()["error"]
    assert "distinct-marker-register789" not in res.get_json()["error"]
    assert "distinct-marker-register789" in caplog.text


def test_login_failure_returns_generic_error_and_logs_exception(client, make_user, monkeypatch, caplog):
    make_user("loginboom@example.com", password="password123")
    import backend.app as app_module

    def _boom(*args, **kwargs):
        raise RuntimeError("distinct-marker-login789")

    monkeypatch.setattr(app_module.users_col, "find_one", _boom)

    with caplog.at_level("ERROR"):
        res = client.post(
            "/api/auth/login",
            json={"email": "loginboom@example.com", "password": "password123"},
        )

    assert res.status_code == 500
    assert "distinct-marker-login789" not in res.get_json()["error"]
    assert "distinct-marker-login789" in caplog.text


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


def test_login_rate_limited_by_ip(client, make_user):
    make_user("throttle1@example.com", password="password123")
    first = client.post(
        "/api/auth/login", json={"email": "throttle1@example.com", "password": "password123"}
    )
    second = client.post(
        "/api/auth/login", json={"email": "throttle1@example.com", "password": "password123"}
    )
    assert first.status_code == 200
    assert second.status_code == 429


def test_login_rate_limit_blocks_regardless_of_credentials(client, make_user):
    """Even a wrong-password retry should be throttled — the limit exists to
    slow brute-force attempts, so it must not distinguish good vs. bad
    credentials."""
    make_user("throttle2@example.com", password="password123")
    client.post("/api/auth/login", json={"email": "throttle2@example.com", "password": "wrong"})
    second = client.post(
        "/api/auth/login", json={"email": "throttle2@example.com", "password": "password123"}
    )
    assert second.status_code == 429


def test_register_rate_limited_by_ip(client):
    first = client.post(
        "/api/auth/register", json={"email": "throttle3@example.com", "password": "password123"}
    )
    second = client.post(
        "/api/auth/register", json={"email": "throttle4@example.com", "password": "password123"}
    )
    assert first.status_code == 200
    assert second.status_code == 429


def test_login_and_register_rate_limit_buckets_are_independent(client, make_user):
    make_user("throttle5@example.com", password="password123")
    login_res = client.post(
        "/api/auth/login", json={"email": "throttle5@example.com", "password": "password123"}
    )
    register_res = client.post(
        "/api/auth/register", json={"email": "throttle6@example.com", "password": "password123"}
    )
    assert login_res.status_code == 200
    assert register_res.status_code != 429


def test_login_allowed_again_after_cooldown_elapses(client, make_user, monkeypatch):
    import backend.app as app_module

    make_user("throttle7@example.com", password="password123")
    first = client.post(
        "/api/auth/login", json={"email": "throttle7@example.com", "password": "password123"}
    )
    assert first.status_code == 200

    # Werkzeug's test client defaults REMOTE_ADDR to 127.0.0.1.
    future = app_module._last_login_time_by_ip["127.0.0.1"]
    monkeypatch.setattr(
        app_module.time, "monotonic", lambda: future + app_module.MIN_SECONDS_BETWEEN_AUTH_REQUESTS + 1
    )
    second = client.post(
        "/api/auth/login", json={"email": "throttle7@example.com", "password": "password123"}
    )
    assert second.status_code == 200


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
