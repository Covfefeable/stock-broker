from flask import Flask

from app.config import get_config
from app.extensions import celery_app, cors, db, init_celery, migrate
from app.models import Country, EventLog, Exchange, IndexAsset, Setting, Stock, StockDailyBar, User
from app.routes import register_routes

celery = celery_app


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    init_celery(app)

    register_routes(app)
    from app import tasks  # noqa: F401

    return app


flask_app = create_app()
