from celery import current_task
from celery.exceptions import SoftTimeLimitExceeded

from app.extensions import celery_app, db
from app.models.event_log import EventLog
from app.models.user import User
from app.services.data_center_service import (
    DataSyncError,
    SYNC_ITEM_COUNTRY_LIST,
    SYNC_ITEM_EXCHANGE_LIST,
    SYNC_ITEM_INDEX_DAILY_HISTORY,
    SYNC_ITEM_INDEX_LIST,
    SYNC_ITEM_STOCK_DAILY_HISTORY,
    SYNC_ITEM_STOCK_LIST,
    SYNC_ITEM_TRADING_CALENDAR,
    batch_sync_stock_and_index_daily_history,
    batch_sync_stock_daily_history,
    log_event,
    sync_country_list,
    sync_exchange_list,
    sync_index_daily_history,
    sync_index_list,
    sync_stock_daily_history,
    sync_stock_list,
    sync_trading_calendar,
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
    _log_task_running(user, task_id, sync_item)

    try:
        if sync_item == SYNC_ITEM_COUNTRY_LIST:
            return sync_country_list(user, task_id=task_id)
        if sync_item == SYNC_ITEM_EXCHANGE_LIST:
            return sync_exchange_list(user, task_id=task_id)
        if sync_item == SYNC_ITEM_STOCK_LIST:
            return sync_stock_list(user, exchange_code or "", task_id=task_id)
        if sync_item == SYNC_ITEM_INDEX_LIST:
            return sync_index_list(user, country_code or "", task_id=task_id)
        if sync_item == SYNC_ITEM_TRADING_CALENDAR:
            return sync_trading_calendar(user, exchange_code or "", task_id=task_id)
        if sync_item == SYNC_ITEM_STOCK_DAILY_HISTORY:
            return sync_stock_daily_history(
                user=user,
                exchange_code=exchange_code or "",
                ticker=ticker or "",
                date_mode=date_mode or "auto_fill",
                start_date=start_date,
                end_date=end_date,
                task_id=task_id,
            )
        if sync_item == SYNC_ITEM_INDEX_DAILY_HISTORY:
            return sync_index_daily_history(
                user=user,
                country_code=country_code or "",
                ticker=ticker or "",
                date_mode=date_mode or "auto_fill",
                start_date=start_date,
                end_date=end_date,
                task_id=task_id,
            )
        raise DataSyncError(f"暂不支持同步项：{sync_item}")
    except DataSyncError as exc:
        _log_task_failed(user, task_id, sync_item, str(exc))
        raise
    except SoftTimeLimitExceeded as exc:
        _log_task_timeout(user, task_id, sync_item)
        raise DataSyncError("同步任务超时") from exc
    except Exception as exc:
        _log_task_failed(user, task_id, sync_item, f"{sync_item_label(sync_item)}任务执行失败：{exc}")
        raise


@celery_app.task(name="app.tasks.data_center.batch_sync_stock_daily_history")
def batch_sync_stock_daily_history_task(*, user_id: int) -> dict:
    user = _get_user(user_id)
    task_id = current_task.request.id if current_task else None
    _log_task_running(user, task_id, SYNC_ITEM_STOCK_DAILY_HISTORY, batch=True)

    try:
        return batch_sync_stock_daily_history(user, task_id=task_id)
    except DataSyncError as exc:
        _log_task_failed(user, task_id, SYNC_ITEM_STOCK_DAILY_HISTORY, str(exc), batch=True)
        raise
    except SoftTimeLimitExceeded as exc:
        log_event(
            user=user,
            task_id=task_id,
            event_type="data_sync_batch",
            event_name="batch_sync_stock_daily_history",
            source="worker",
            target=SYNC_ITEM_STOCK_DAILY_HISTORY,
            status="failed",
            level="error",
            message="批量同步股票日线任务执行超时。",
        )
        raise DataSyncError("批量同步股票日线任务超时") from exc
    except Exception as exc:
        _log_task_failed(user, task_id, SYNC_ITEM_STOCK_DAILY_HISTORY, f"批量同步股票日线任务执行失败：{exc}", batch=True)
        raise


@celery_app.task(name="app.tasks.data_center.batch_sync_stock_and_index_daily_history")
def batch_sync_stock_and_index_daily_history_task(*, user_id: int) -> dict:
    user = _get_user(user_id)
    task_id = current_task.request.id if current_task else None
    log_event(
        user=user,
        task_id=task_id,
        event_type="data_sync_batch",
        event_name="batch_sync_stock_and_index_daily_history",
        source="worker",
        target=SYNC_ITEM_STOCK_DAILY_HISTORY,
        status="running",
        level="info",
        message="批量同步股票/指数日线任务开始执行。",
    )

    try:
        return batch_sync_stock_and_index_daily_history(user, task_id=task_id)
    except DataSyncError as exc:
        _log_task_failed(user, task_id, SYNC_ITEM_STOCK_DAILY_HISTORY, str(exc), batch=True)
        raise
    except SoftTimeLimitExceeded as exc:
        log_event(
            user=user,
            task_id=task_id,
            event_type="data_sync_batch",
            event_name="batch_sync_stock_and_index_daily_history",
            source="worker",
            target=SYNC_ITEM_STOCK_DAILY_HISTORY,
            status="failed",
            level="error",
            message="批量同步股票/指数日线任务执行超时。",
        )
        raise DataSyncError("批量同步股票/指数日线任务超时") from exc
    except Exception as exc:
        _log_task_failed(user, task_id, SYNC_ITEM_STOCK_DAILY_HISTORY, f"批量同步股票/指数日线任务执行失败：{exc}", batch=True)
        raise


def _log_task_running(
    user: User,
    task_id: str | None,
    sync_item: str,
    *,
    batch: bool = False,
) -> None:
    event_name_map = {
        SYNC_ITEM_COUNTRY_LIST: "sync_country_list",
        SYNC_ITEM_EXCHANGE_LIST: "sync_exchange_list",
        SYNC_ITEM_STOCK_LIST: "sync_stock_list",
        SYNC_ITEM_INDEX_LIST: "sync_index_list",
        SYNC_ITEM_TRADING_CALENDAR: "sync_trading_calendar",
        SYNC_ITEM_STOCK_DAILY_HISTORY: "sync_stock_daily_history",
        SYNC_ITEM_INDEX_DAILY_HISTORY: "sync_index_daily_history",
    }
    label_map = {
        SYNC_ITEM_COUNTRY_LIST: "国家/地区清单",
        SYNC_ITEM_EXCHANGE_LIST: "交易所清单",
        SYNC_ITEM_STOCK_LIST: "股票清单",
        SYNC_ITEM_INDEX_LIST: "指数清单",
        SYNC_ITEM_TRADING_CALENDAR: "交易日历",
        SYNC_ITEM_STOCK_DAILY_HISTORY: "股票历史日线",
        SYNC_ITEM_INDEX_DAILY_HISTORY: "指数历史日线",
    }
    log_event(
        user=user,
        task_id=task_id,
        event_type="data_sync_batch" if batch else "data_sync",
        event_name="batch_sync_stock_daily_history" if batch else event_name_map.get(sync_item, sync_item),
        source="worker",
        target=sync_item,
        status="running",
        level="info",
        message=f"{label_map.get(sync_item, sync_item)}任务开始执行。",
    )


def _log_task_timeout(user: User, task_id: str | None, sync_item: str) -> None:
    label_map = {
        SYNC_ITEM_COUNTRY_LIST: "国家/地区清单",
        SYNC_ITEM_EXCHANGE_LIST: "交易所清单",
        SYNC_ITEM_STOCK_LIST: "股票清单",
        SYNC_ITEM_INDEX_LIST: "指数清单",
        SYNC_ITEM_TRADING_CALENDAR: "交易日历",
        SYNC_ITEM_STOCK_DAILY_HISTORY: "股票历史日线",
        SYNC_ITEM_INDEX_DAILY_HISTORY: "指数历史日线",
    }
    event_name_map = {
        SYNC_ITEM_COUNTRY_LIST: "sync_country_list",
        SYNC_ITEM_EXCHANGE_LIST: "sync_exchange_list",
        SYNC_ITEM_STOCK_LIST: "sync_stock_list",
        SYNC_ITEM_INDEX_LIST: "sync_index_list",
        SYNC_ITEM_TRADING_CALENDAR: "sync_trading_calendar",
        SYNC_ITEM_STOCK_DAILY_HISTORY: "sync_stock_daily_history",
        SYNC_ITEM_INDEX_DAILY_HISTORY: "sync_index_daily_history",
    }
    log_event(
        user=user,
        task_id=task_id,
        event_type="data_sync",
        event_name=event_name_map.get(sync_item, sync_item),
        source="worker",
        target=sync_item,
        status="failed",
        level="error",
        message=f"{label_map.get(sync_item, sync_item)}任务执行超时。",
    )


def _log_task_failed(
    user: User,
    task_id: str | None,
    sync_item: str,
    message: str,
    *,
    batch: bool = False,
) -> None:
    if task_id:
        existing_failure = (
            EventLog.query.filter_by(task_id=task_id, status="failed")
            .order_by(EventLog.id.desc())
            .first()
        )
        if existing_failure:
            return

    event_name_map = {
        SYNC_ITEM_COUNTRY_LIST: "sync_country_list",
        SYNC_ITEM_EXCHANGE_LIST: "sync_exchange_list",
        SYNC_ITEM_STOCK_LIST: "sync_stock_list",
        SYNC_ITEM_INDEX_LIST: "sync_index_list",
        SYNC_ITEM_TRADING_CALENDAR: "sync_trading_calendar",
        SYNC_ITEM_STOCK_DAILY_HISTORY: "sync_stock_daily_history",
        SYNC_ITEM_INDEX_DAILY_HISTORY: "sync_index_daily_history",
    }
    log_event(
        user=user,
        task_id=task_id,
        event_type="data_sync_batch" if batch else "data_sync",
        event_name="batch_sync_stock_daily_history" if batch else event_name_map.get(sync_item, sync_item),
        source="worker",
        target=sync_item,
        status="failed",
        level="error",
        message=message,
    )
