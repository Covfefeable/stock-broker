from flask import Flask

from app.routes.auth import auth_bp
from app.routes.health import health_bp


def register_routes(app: Flask) -> None:
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api")
