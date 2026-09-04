from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from .routes.admin import admin_bp
from .routes.auth import auth_bp
from .routes.chat import chat_bp
from .routes.documents import documents_bp
from .routes.health import health_bp


def create_app() -> Flask:
    flask_app = Flask(__name__)
    # Backend is never publicly exposed — nginx is the only thing that ever
    # connects to it, both in docker-compose and on Railway's private network —
    # so trusting exactly one proxy hop for the client's real IP is correct.
    flask_app.wsgi_app = ProxyFix(flask_app.wsgi_app, x_for=1, x_proto=0, x_host=0, x_port=0, x_prefix=0)
    for blueprint in (health_bp, auth_bp, documents_bp, chat_bp, admin_bp):
        flask_app.register_blueprint(blueprint)
    return flask_app
