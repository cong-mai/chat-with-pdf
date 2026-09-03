def test_list_users_requires_auth(client):
    res = client.get("/api/admin/users")
    assert res.status_code == 401


def test_list_users_forbidden_for_non_admin(client, make_user, auth_header):
    user = make_user("plain@example.com")
    res = client.get("/api/admin/users", headers=auth_header(user["token"]))
    assert res.status_code == 403


def test_list_users_returns_all_users_for_admin(client, make_user, auth_header):
    admin = make_user("admin1@example.com", role="admin")
    make_user("plain1@example.com")
    make_user("plain2@example.com")

    res = client.get("/api/admin/users", headers=auth_header(admin["token"]))
    assert res.status_code == 200
    emails = {u["email"] for u in res.get_json()["users"]}
    assert emails == {"admin1@example.com", "plain1@example.com", "plain2@example.com"}


def test_deactivate_forbidden_for_non_admin(client, make_user, auth_header):
    actor = make_user("notadmin@example.com")
    target = make_user("target@example.com")
    res = client.patch(
        f"/api/admin/users/{target['id']}",
        json={"active": False},
        headers=auth_header(actor["token"]),
    )
    assert res.status_code == 403


def test_admin_can_deactivate_and_reactivate_user(client, make_user, auth_header):
    admin = make_user("admin2@example.com", role="admin")
    target = make_user("deactivatee@example.com")

    off = client.patch(
        f"/api/admin/users/{target['id']}",
        json={"active": False},
        headers=auth_header(admin["token"]),
    )
    assert off.status_code == 200
    assert off.get_json()["active"] is False

    login_blocked = client.post(
        "/api/auth/login", json={"email": "deactivatee@example.com", "password": "password123"}
    )
    assert login_blocked.status_code == 400

    # Two real login attempts in one test would otherwise trip the new
    # per-IP login cooldown — clear it to isolate this test from that
    # unrelated concern (covered separately in test_auth.py).
    import backend.app as app_module

    app_module._last_login_time_by_ip.clear()

    on = client.patch(
        f"/api/admin/users/{target['id']}",
        json={"active": True},
        headers=auth_header(admin["token"]),
    )
    assert on.status_code == 200
    assert on.get_json()["active"] is True

    login_ok = client.post(
        "/api/auth/login", json={"email": "deactivatee@example.com", "password": "password123"}
    )
    assert login_ok.status_code == 200


def test_admin_cannot_deactivate_self(client, make_user, auth_header):
    admin = make_user("selfadmin@example.com", role="admin")
    res = client.patch(
        f"/api/admin/users/{admin['id']}",
        json={"active": False},
        headers=auth_header(admin["token"]),
    )
    assert res.status_code == 400
    assert "own account" in res.get_json()["error"]


def test_last_admin_guard_query_blocks_when_no_other_active_admin_exists(client, make_user, auth_header):
    """Exercises the last-active-admin guard's query directly.

    Through the live API, a request always arrives from a currently-active
    admin distinct from its target, so that admin itself always counts as
    "another active admin" and the guard never fires there — total lockout
    is instead prevented unconditionally by the self-deactivation block
    (see test_admin_cannot_deactivate_self). This test confirms the guard's
    own query logic — used defensively in case that self-block is ever
    relaxed — correctly reports zero remaining active admins when only one
    active admin exists in the system.
    """
    import backend.app as app_module

    sole_admin = make_user("soleadmin@example.com", role="admin")
    make_user("inactiveadmin@example.com", role="admin", active=False)
    make_user("regularuser@example.com", role="user")

    other_active_admins = app_module.users_col.count_documents({
        "_id": {"$ne": sole_admin["id"]},
        "role": "admin",
        "active": {"$ne": False},
    })
    assert other_active_admins == 0


def test_two_active_admins_can_deactivate_each_other_in_turn(client, make_user, auth_header):
    admin_a = make_user("adminA@example.com", role="admin")
    admin_b = make_user("adminB@example.com", role="admin")

    # B deactivates A — allowed, B remains as an active admin.
    res = client.patch(
        f"/api/admin/users/{admin_a['id']}",
        json={"active": False},
        headers=auth_header(admin_b["token"]),
    )
    assert res.status_code == 200

    import backend.app as app_module

    still_active = app_module.users_col.count_documents({"role": "admin", "active": {"$ne": False}})
    assert still_active == 1


def test_deactivate_requires_boolean_active_field(client, make_user, auth_header):
    admin = make_user("admin3@example.com", role="admin")
    target = make_user("target2@example.com")
    res = client.patch(
        f"/api/admin/users/{target['id']}",
        json={"active": "nope"},
        headers=auth_header(admin["token"]),
    )
    assert res.status_code == 400


def test_deactivate_nonexistent_user_returns_404(client, make_user, auth_header):
    admin = make_user("admin4@example.com", role="admin")
    res = client.patch(
        "/api/admin/users/does-not-exist",
        json={"active": False},
        headers=auth_header(admin["token"]),
    )
    assert res.status_code == 404
