from celery import current_task

from app.extensions import celery_app
from app.services.data_center_service import check_canghai_data_source_status


@celery_app.task(name="app.tasks.scheduled.check_canghai_data_source_status")
def check_canghai_data_source_status_task() -> dict:
    task_id = current_task.request.id if current_task else None
    return check_canghai_data_source_status(task_id=task_id)
