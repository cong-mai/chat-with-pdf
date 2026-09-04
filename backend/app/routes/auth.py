import uuid
from datetime import UTC, datetime

from flask import Blueprint, g, jsonify, request
from pymongo.errors import DuplicateKeyError
from werkzeug.security import check_password_hash, generate_password_hash

from .. import config, extensions, rate_limit, security

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/api/auth/register")
def register():
    ip = request.remote_addr
    if rate_limit.too_soon(
        rate_limit._last_register_time_by_ip, ip, config.MIN_SECONDS_BETWEEN_AUTH_REQUESTS
    ):
        return jsonify(error="Give it a moment before trying again."), 429

    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not config.EMAIL_RE.match(email):
        return jsonify(error="Enter a valid email address."), 400
    if len(password) < 8:
        return jsonify(error="Passwords need at least 8 characters."), 400

    user_doc = {
        "_id": str(uuid.uuid4()),
        "email": email,
        "password_hash": generate_password_hash(password),
        "role": "user",
        "active": True,
        "created_at": datetime.now(UTC),
    }
    try:
        extensions.users_col.insert_one(user_doc)
    except DuplicateKeyError:
        return jsonify(error="That email is already registered."), 400
    except Exception:
        config.logger.exception("Registration failed for %s", email)
        return jsonify(error="Something went wrong. Please try again."), 500

    user = {"id": user_doc["_id"], "email": email, "role": "user"}
    return jsonify(token=security._issue_token(user), user=user)


@auth_bp.post("/api/auth/login")
def login():
    ip = request.remote_addr
    if rate_limit.too_soon(
        rate_limit._last_login_time_by_ip, ip, config.MIN_SECONDS_BETWEEN_AUTH_REQUESTS
    ):
        return jsonify(error="Give it a moment before trying again."), 429

    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    try:
        user_doc = extensions.users_col.find_one({"email": email})
        if not user_doc or not check_password_hash(user_doc["password_hash"], password):
            return jsonify(error="Invalid email or password."), 400
        if user_doc.get("active") is False:
            return jsonify(error="This account has been deactivated."), 400

        user = {"id": user_doc["_id"], "email": user_doc["email"], "role": user_doc["role"]}
        return jsonify(token=security._issue_token(user), user=user)
    except Exception:
        config.logger.exception("Login failed for %s", email)
        return jsonify(error="Something went wrong. Please try again."), 500


@auth_bp.get("/api/auth/me")
@security.require_auth
def me():
    return jsonify(user=g.user)
