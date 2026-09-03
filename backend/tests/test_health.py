from unittest.mock import patch


def test_health_ok_when_mongo_reachable(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


def test_health_no_auth_required(client):
    """The health endpoint must be reachable with no Authorization header —
    orchestration/monitoring tools won't have credentials."""
    res = client.get("/api/health")
    assert res.status_code != 401


def test_health_reports_error_when_mongo_unreachable(client):
    import backend.app as app_module

    with patch.object(
        app_module.mongo_client.admin, "command", side_effect=RuntimeError("mongo is down")
    ):
        res = client.get("/api/health")

    assert res.status_code == 503
    assert res.get_json()["status"] == "error"


def test_health_not_rate_limited(client):
    """Unlike auth endpoints, health checks may be polled frequently and
    must not be throttled."""
    first = client.get("/api/health")
    second = client.get("/api/health")
    assert first.status_code == 200
    assert second.status_code == 200
