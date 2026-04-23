from celery import Celery, Task
from flask_cors import CORS
from flask_migrate import Migrate
from flask_sock import Sock
from flask_sqlalchemy import SQLAlchemy
from redis import Redis

db = SQLAlchemy()
migrate = Migrate()
cors = CORS()
sock = Sock()
celery_app = Celery(__name__)
redis_client: Redis | None = None


def init_celery(app):
    class FlaskTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app.config_from_object(
        {
            "broker_url": app.config["CELERY_BROKER_URL"],
            "result_backend": app.config["CELERY_RESULT_BACKEND"],
            "task_ignore_result": False,
            "task_track_started": True,
        }
    )
    celery_app.Task = FlaskTask
    return celery_app


def init_redis(app):
    global redis_client
    redis_client = Redis.from_url(app.config["REDIS_URL"], decode_responses=True)
    return redis_client
