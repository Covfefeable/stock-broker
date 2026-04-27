from datetime import datetime

from celery.exceptions import TimeoutError
from flask import Blueprint, g, request

from app.extensions import celery_app
from app.routes.auth import auth_required
from app.services.event_logs import EVENT_CATEGORY_SYNC, sync_item_label
from app.services.data_center import (
    DATE_MODE_AUTO_FILL,
    SYNC_ITEM_COUNTRY_LIST,
    SYNC_ITEM_EXCHANGE_LIST,
    SYNC_ITEM_INDEX_DAILY_HISTORY,
    SYNC_ITEM_INDEX_LIST,
    SYNC_ITEM_STOCK_DAILY_HISTORY,
    SYNC_ITEM_STOCK_LIST,
    SYNC_ITEM_TRADING_CALENDAR,
    get_data_center_overview_metrics,
    get_index_daily_coverage,
    get_index_browser_bars,
    get_stock_daily_coverage,
    get_stock_browser_bars,
    list_trading_calendar_entries,
    list_country_options,
    list_exchange_options,
    list_index_options,
    list_recent_event_logs,
    list_stock_options,
    log_event,
)
from app.services.settings import get_canghai_token_status
from app.tasks.data_center import (
    batch_sync_stock_and_index_daily_history_task,
    sync_data_center_item,
)

data_center_bp = Blueprint("data_center", __name__)


@data_center_bp.get("/data-center/overview")
@auth_required
def overview():
    return {"metrics": get_data_center_overview_metrics()}


@data_center_bp.get("/data-center/event-logs")
@auth_required
def event_logs():
    offset = max(int(str(request.args.get("offset") or "0")), 0)
    limit = min(max(int(str(request.args.get("limit") or "20")), 1), 100)
    return list_recent_event_logs(offset=offset, limit=limit, category=EVENT_CATEGORY_SYNC)


@data_center_bp.get("/data-center/source-status")
@auth_required
def source_status():
    status = get_canghai_token_status(g.current_user)
    detail = status["status"]
    return {
        "item": {
            "sourceKey": status["sourceKey"],
            "sourceName": status["sourceName"],
            "status": detail["status"],
            "tokenStatus": detail["tokenStatus"],
            "latencyMs": detail["latencyMs"],
            "checkedAt": detail["lastCheckedAt"],
            "httpStatus": detail["httpStatus"],
            "message": detail["message"],
        }
    }


@data_center_bp.get("/data-center/exchange-options")
@auth_required
def exchange_options():
    return {"items": list_exchange_options()}


@data_center_bp.get("/data-center/country-options")
@auth_required
def country_options():
    return {"items": list_country_options()}


@data_center_bp.get("/data-center/stock-options")
@auth_required
def stock_options():
    exchange_code = str(request.args.get("exchangeCode") or "").strip()
    return {"items": list_stock_options(exchange_code=exchange_code)}


@data_center_bp.get("/data-center/index-options")
@auth_required
def index_options():
    country_code = str(request.args.get("countryCode") or "").strip()
    return {"items": list_index_options(country_code=country_code)}


@data_center_bp.get("/data-center/trading-calendar")
@auth_required
def trading_calendar():
    exchange_code = str(request.args.get("exchangeCode") or "").strip()
    year = int(str(request.args.get("year") or datetime.now().year))
    month = int(str(request.args.get("month") or datetime.now().month))
    return {
        "items": list_trading_calendar_entries(exchange_code=exchange_code, year=year, month=month)
    }


@data_center_bp.get("/data-center/stock-daily-coverage")
@auth_required
def stock_daily_coverage():
    exchange_code = str(request.args.get("exchangeCode") or "").strip()
    ticker = str(request.args.get("ticker") or "").strip()
    return {"coverage": get_stock_daily_coverage(exchange_code, ticker)}


@data_center_bp.get("/data-center/index-daily-coverage")
@auth_required
def index_daily_coverage():
    country_code = str(request.args.get("countryCode") or "").strip()
    ticker = str(request.args.get("ticker") or "").strip()
    return {"coverage": get_index_daily_coverage(country_code, ticker)}


@data_center_bp.get("/data-center/browser/stock-bars")
@auth_required
def stock_browser_bars():
    exchange_code = str(request.args.get("exchangeCode") or "").strip()
    ticker = str(request.args.get("ticker") or "").strip()
    return get_stock_browser_bars(exchange_code, ticker)


@data_center_bp.get("/data-center/browser/index-bars")
@auth_required
def index_browser_bars():
    country_code = str(request.args.get("countryCode") or "").strip()
    ticker = str(request.args.get("ticker") or "").strip()
    return get_index_browser_bars(country_code, ticker)


@data_center_bp.get("/tasks/<task_id>")
@auth_required
def task_status(task_id: str):
    task = celery_app.AsyncResult(task_id)
    payload = {
        "taskId": task_id,
        "state": task.state,
        "ready": task.ready(),
        "successful": task.successful() if task.ready() else False,
        "failed": task.failed() if task.ready() else False,
    }

    if task.ready():
        try:
            result = task.get(propagate=False, timeout=0.1)
        except TimeoutError:
            result = None

        if task.successful():
            payload["result"] = result
        else:
            payload["error"] = serialize_task_error(result)

    return payload


@data_center_bp.post("/data-center/sync")
@auth_required
def sync_data():
    payload = request.get_json(silent=True) or {}
    sync_item = str(payload.get("syncItem") or "").strip()
    exchange_code = str(payload.get("exchangeCode") or "").strip()
    country_code = str(payload.get("countryCode") or "").strip()
    ticker = str(payload.get("ticker") or "").strip()
    date_mode = str(payload.get("dateMode") or DATE_MODE_AUTO_FILL).strip()
    start_date = str(payload.get("startDate") or "").strip()
    end_date = str(payload.get("endDate") or "").strip()

    if sync_item not in {
        SYNC_ITEM_COUNTRY_LIST,
        SYNC_ITEM_EXCHANGE_LIST,
        SYNC_ITEM_STOCK_LIST,
        SYNC_ITEM_INDEX_LIST,
        SYNC_ITEM_TRADING_CALENDAR,
        SYNC_ITEM_STOCK_DAILY_HISTORY,
        SYNC_ITEM_INDEX_DAILY_HISTORY,
    }:
        return {"message": f"暂不支持同步项：{sync_item_label(sync_item or 'unknown')}"}, 400

    task = sync_data_center_item.apply_async(
        kwargs={
            "user_id": g.current_user.id,
            "sync_item": sync_item,
            "exchange_code": exchange_code or None,
            "country_code": country_code or None,
            "ticker": ticker or None,
            "date_mode": date_mode,
            "start_date": start_date or None,
            "end_date": end_date or None,
        }
    )
    log_event(
        user=g.current_user,
        task_id=task.id,
        event_type="data_sync",
        event_name="enqueue_sync_task",
        source="api",
        target=sync_item,
        status="queued",
        level="info",
        message=f"{sync_item_label(sync_item)}任务已提交，等待后台执行。",
    )
    return {
        "message": f"{sync_item_label(sync_item)}任务已提交",
        "taskId": task.id,
    }, 202


@data_center_bp.post("/data-center/sync/assets/batch-auto-fill")
@auth_required
def batch_sync_assets():
    task = batch_sync_stock_and_index_daily_history_task.apply_async(
        kwargs={"user_id": g.current_user.id}
    )
    log_event(
        user=g.current_user,
        task_id=task.id,
        event_type="data_sync_batch",
        event_name="enqueue_batch_sync_stock_and_index_daily_history",
        source="api",
        target=SYNC_ITEM_STOCK_DAILY_HISTORY,
        status="queued",
        level="info",
        message="批量同步股票/指数日线任务已提交，等待后台执行。",
    )
    return {
        "message": "批量同步股票/指数日线任务已提交",
        "taskId": task.id,
    }, 202


def serialize_task_error(result: object) -> str:
    if result is None:
        return "任务执行失败"
    if isinstance(result, Exception):
        return str(result)
    return str(result)
