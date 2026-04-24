from flask import Flask

from app.config import get_config
from app.extensions import celery_app, cors, db, init_celery, init_redis, migrate, sock
from app.models import Country, EventLog, Exchange, IndexAsset, Setting, Stock, StockDailyBar, Strategy, User
from app.routes import register_routes

celery = celery_app


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    sock.init_app(app)
    init_celery(app)
    init_redis(app)

    register_routes(app)
    from app import tasks  # noqa: F401

    return app


flask_app = create_app()
