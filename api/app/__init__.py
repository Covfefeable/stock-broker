from flask import Flask

from app.config import get_config
from app.extensions import cors, db, migrate
from app.routes import register_routes


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    register_routes(app)

    return app

