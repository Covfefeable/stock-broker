from celery import current_task

from app.extensions import celery_app, db
from app.models.user import User
from app.services.data_center_service import (
    DataSyncError,
    sync_country_list,
    sync_exchange_list,
    sync_index_list,
    sync_stock_daily_history,
    sync_stock_list,
    batch_sync_stock_daily_history,
)


def _get_user(user_id: int) -> User:
    user = db.session.get(User, user_id)
    if not user:
        raise DataSyncError(f"未找到用户 {user_id}，无法执行同步任务。")
    return user


@celery_app.task(name="app.tasks.data_center.sync_data_center_item")
def sync_data_center_item(
    *,
    user_id: int,
    sync_item: str,
    exchange_code: str | None = None,
    country_code: str | None = None,
    ticker: str | None = None,
    date_mode: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    user = _get_user(user_id)
    task_id = current_task.request.id if current_task else None

    if sync_item == "country_list":
        return sync_country_list(user, task_id=task_id)
    if sync_item == "exchange_list":
        return sync_exchange_list(user, task_id=task_id)
    if sync_item == "stock_list":
        return sync_stock_list(user, exchange_code or "", task_id=task_id)
    if sync_item == "index_list":
        return sync_index_list(user, country_code or "", task_id=task_id)
    if sync_item == "stock_daily_history":
        return sync_stock_daily_history(
            user=user,
            exchange_code=exchange_code or "",
            ticker=ticker or "",
            date_mode=date_mode or "auto_fill",
            start_date=start_date,
            end_date=end_date,
            task_id=task_id,
        )
    raise DataSyncError(f"暂不支持同步项：{sync_item}")


@celery_app.task(name="app.tasks.data_center.batch_sync_stock_daily_history")
def batch_sync_stock_daily_history_task(*, user_id: int) -> dict:
    user = _get_user(user_id)
    task_id = current_task.request.id if current_task else None
    return batch_sync_stock_daily_history(user, task_id=task_id)
