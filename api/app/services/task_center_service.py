import json
import time
from collections import OrderedDict, defaultdict

from app import extensions
from app.models.event_log import EventLog

TASK_CENTER_CHANNEL = "task_center.events"


def list_recent_task_summaries(*, user_id: int, limit: int = 30) -> list[dict]:
    rows = (
        EventLog.query.filter(
            EventLog.user_id == user_id,
            EventLog.task_id.isnot(None),
            EventLog.show_in_ui.is_(True),
        )
        .order_by(EventLog.created_at.desc(), EventLog.id.desc())
        .limit(max(limit * 6, 60))
        .all()
    )

    task_map: "OrderedDict[str, EventLog]" = OrderedDict()
    log_map: dict[str, list[str]] = defaultdict(list)

    for row in rows:
        if not row.task_id:
            continue
        if row.task_id not in task_map:
            task_map[row.task_id] = row
        if len(log_map[row.task_id]) < 3 and row.message:
            log_map[row.task_id].append(row.message)
        if len(task_map) >= limit and all(len(items) >= 3 for items in log_map.values()):
            break

    items = []
    for task_id, latest in task_map.items():
        items.append(_build_task_summary(latest, list(reversed(log_map[task_id]))))
    return items


def publish_task_event(log: EventLog) -> None:
    if extensions.redis_client is None or not log.task_id or not log.show_in_ui:
        return

    payload = {
        "type": "task.updated",
        "userId": log.user_id,
        "payload": _build_task_summary(log, [log.message] if log.message else []),
    }
    extensions.redis_client.publish(TASK_CENTER_CHANNEL, json.dumps(payload, ensure_ascii=False))


def subscribe_task_events():
    if extensions.redis_client is None:
        raise RuntimeError("Redis client is not initialized.")

    pubsub = extensions.redis_client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(TASK_CENTER_CHANNEL)
    return pubsub


def iter_task_events(pubsub):
    while True:
        message = pubsub.get_message(timeout=1.0)
        if message and message.get("data"):
            yield message["data"]
        else:
            time.sleep(0.2)


def _build_task_summary(log: EventLog, logs: list[str]) -> dict:
    created_at = log.created_at.isoformat() if log.created_at else None
    started_at = log.started_at.isoformat() if log.started_at else created_at
    finished_at = log.finished_at.isoformat() if log.finished_at else None
    updated_at = finished_at or created_at

    return {
        "taskId": log.task_id,
        "name": task_name_from_log(log),
        "type": task_type_from_log(log),
        "status": task_status_from_log(log),
        "startedAt": started_at,
        "updatedAt": updated_at,
        "progressText": log.message,
        "recordsAffected": log.records_affected,
        "durationMs": log.duration_ms,
        "logs": logs,
    }


def task_name_from_log(log: EventLog) -> str:
    event_name = log.event_name or ""
    target = log.target or ""

    if event_name == "enqueue_batch_sync_stock_daily_history":
        return "批量同步股票日线"
    if event_name == "batch_sync_stock_daily_history":
        return "批量同步股票日线"
    if event_name in {"enqueue_sync_task", "sync_country_list"} or target == "country_list":
        return "国家/地区清单同步"
    if event_name == "sync_exchange_list" or target == "exchange_list":
        return "交易所清单同步"
    if event_name == "sync_stock_list" or target == "stock_list":
        return "股票清单同步"
    if event_name == "sync_index_list" or target == "index_list":
        return "指数清单同步"
    if event_name == "sync_trading_calendar" or target == "trading_calendar":
        return "交易日历同步"
    if event_name == "sync_index_daily_history" or target == "index_daily_history":
        return "指数历史日线同步"
    if event_name == "sync_stock_daily_history" or target == "stock_daily_history":
        return "股票历史日线同步"
    return event_name or "任务"


def task_type_from_log(log: EventLog) -> str:
    event_type = (log.event_type or "").lower()
    if "agent" in event_type:
        return "agent"
    return "sync"


def task_status_from_log(log: EventLog) -> str:
    status = (log.status or "").lower()
    if status in {"queued", "running", "success", "failure"}:
        return status
    if status == "failed":
        return "failure"
    if status == "partial_success":
        return "success"
    return "queued"
