from celery import current_task

from app.extensions import celery_app
from app.services.scheduled_plans import scan_due_scheduled_plans
from app.services.settings import scan_online_canghai_token_statuses


@celery_app.task(name="app.tasks.scheduled.scan_online_canghai_token_statuses")
def scan_online_canghai_token_statuses_task() -> dict:
    task_id = current_task.request.id if current_task else None
    return scan_online_canghai_token_statuses(task_id=task_id)


@celery_app.task(name="app.tasks.scheduled.scan_due_scheduled_plans")
def scan_due_scheduled_plans_task() -> dict:
    task_id = current_task.request.id if current_task else None
    return scan_due_scheduled_plans(task_id=task_id)
