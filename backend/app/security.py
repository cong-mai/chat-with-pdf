"""JWT issuing/verification and the require_auth / require_admin decorators."""

from datetime import UTC, datetime, timedelta
from functools import wraps

import jwt
from flask import g, jsonify, request

from . import config, extensions


def _issue_token(user: dict) -> str:
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "exp": datetime.now(UTC) + timedelta(hours=config.JWT_EXPIRES_HOURS),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify(error="Please log in."), 401
        token = header[len("Bearer "):]
        try:
            payload = jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
        except jwt.PyJWTError:
            return jsonify(error="Please log in."), 401

        # Looked up per-request (not trusted from the token) so a deactivated
        # account is locked out immediately, not just on its next login.
        user_doc = extensions.users_col.find_one({"_id": payload["sub"]})
        if not user_doc or user_doc.get("active") is False:
            return jsonify(error="Please log in."), 401

        g.user = {"id": payload["sub"], "email": payload["email"], "role": payload["role"]}
        return view(*args, **kwargs)

    return wrapped


def require_admin(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user["role"] != "admin":
            return jsonify(error="Admins only."), 403
        return view(*args, **kwargs)

    return wrapped
