from flask import Flask

from app.routes.agent_task import agent_task_bp
from app.routes.auth import auth_bp
from app.routes.dashboard import dashboard_bp
from app.routes.data_center import data_center_bp
from app.routes.health import health_bp
from app.routes.settings import settings_bp
from app.routes.strategy import strategy_bp
from app.routes.task_center import task_center_bp


def register_routes(app: Flask) -> None:
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(agent_task_bp, url_prefix="/api")
    app.register_blueprint(dashboard_bp, url_prefix="/api")
    app.register_blueprint(data_center_bp, url_prefix="/api")
    app.register_blueprint(settings_bp, url_prefix="/api")
    app.register_blueprint(strategy_bp, url_prefix="/api")
    app.register_blueprint(task_center_bp, url_prefix="/api")
