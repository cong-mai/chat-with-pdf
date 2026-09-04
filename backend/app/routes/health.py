from flask import Blueprint, jsonify

from .. import config, extensions

health_bp = Blueprint("health", __name__)


@health_bp.get("/api/health")
def health():
    try:
        extensions.mongo_client.admin.command("ping")
    except Exception:
        config.logger.exception("Health check: Mongo ping failed")
        return jsonify(status="error"), 503
    return jsonify(status="ok")
