from flask import Blueprint, abort, g, jsonify, request

from .. import extensions, security

admin_bp = Blueprint("admin", __name__)


@admin_bp.get("/api/admin/users")
@security.require_auth
@security.require_admin
def list_users():
    users = extensions.users_col.find().sort("created_at", -1)
    return jsonify(users=[
        {
            "id": u["_id"],
            "email": u["email"],
            "role": u["role"],
            "active": u.get("active") is not False,
            "created_at": u["created_at"].isoformat(),
        }
        for u in users
    ])


@admin_bp.patch("/api/admin/users/<user_id>")
@security.require_auth
@security.require_admin
def set_user_active(user_id):
    payload = request.get_json(silent=True) or {}
    if "active" not in payload or not isinstance(payload["active"], bool):
        return jsonify(error="Provide a boolean 'active' value."), 400
    active = payload["active"]

    target = extensions.users_col.find_one({"_id": user_id})
    if not target:
        abort(404)

    if not active:
        if user_id == g.user["id"]:
            return jsonify(error="You can't deactivate your own account."), 400
        if target["role"] == "admin":
            other_active_admins = extensions.users_col.count_documents({
                "_id": {"$ne": user_id},
                "role": "admin",
                "active": {"$ne": False},
            })
            if other_active_admins == 0:
                return jsonify(error="At least one active admin must remain."), 400

    extensions.users_col.update_one({"_id": user_id}, {"$set": {"active": active}})
    updated = extensions.users_col.find_one({"_id": user_id})
    return jsonify(
        id=updated["_id"],
        email=updated["email"],
        role=updated["role"],
        active=updated.get("active") is not False,
        created_at=updated["created_at"].isoformat(),
    )
