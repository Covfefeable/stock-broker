from celery import Celery, Task
from flask_cors import CORS
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
cors = CORS()
celery_app = Celery(__name__)


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
