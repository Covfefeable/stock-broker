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
    sync_task_timeout = int(app.config.get("SYNC_TASK_TIMEOUT_SECONDS", 3600))

    class FlaskTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app.config_from_object(
        {
            "broker_url": app.config["CELERY_BROKER_URL"],
            "result_backend": app.config["CELERY_RESULT_BACKEND"],
            "beat_schedule_filename": app.config["CELERY_BEAT_SCHEDULE_FILENAME"],
            "task_ignore_result": False,
            "task_track_started": True,
            "task_annotations": {
                "app.tasks.data_center.sync_data_center_item": {
                    "soft_time_limit": sync_task_timeout,
                    "time_limit": sync_task_timeout + 30,
                },
                "app.tasks.data_center.batch_sync_stock_daily_history": {
                    "soft_time_limit": sync_task_timeout,
                    "time_limit": sync_task_timeout + 30,
                },
                "app.tasks.agent.run_agent_task": {
                    "soft_time_limit": sync_task_timeout,
                    "time_limit": sync_task_timeout + 30,
                },
                "app.tasks.backtest_lab.run_strategy_evaluation_task": {
                    "soft_time_limit": sync_task_timeout,
                    "time_limit": sync_task_timeout + 30,
                },
            },
            "beat_schedule": {
                "check-canghai-data-source-status-every-5-minutes": {
                    "task": "app.tasks.scheduled.check_canghai_data_source_status",
                    "schedule": 300.0,
                }
            },
        }
    )
    celery_app.Task = FlaskTask
    return celery_app


def init_redis(app):
    global redis_client
    redis_client = Redis.from_url(app.config["REDIS_URL"], decode_responses=True)
    return redis_client
