import json
import time
from collections import OrderedDict, defaultdict

from app import extensions
from app.models.agent_iteration import AgentIteration
from app.models.agent_task import AgentTask
from app.models.event_log import EventLog
from app.services.event_log_meta import event_name_label, sync_item_label

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
    progress_current = None
    progress_total = None
    entity_type = None
    entity_id = None
    agent_payload: dict = {}

    if task_type_from_log(log) == "agent" and log.task_id:
        agent_task = AgentTask.query.filter_by(celery_task_id=log.task_id).first()
        if agent_task:
            progress_current = agent_task.current_iteration
            progress_total = agent_task.max_iterations
            entity_type = "agent_task"
            entity_id = agent_task.id
            best_iteration = best_iteration_for_agent(agent_task)
            agent_payload = {
                "assetName": agent_task.asset_name,
                "assetIdentifier": agent_task.asset_identifier,
                "bestAnnualReturn": _metric_to_float(agent_task.best_annual_return),
                "bestMaxDrawdown": _metric_to_float(best_iteration.max_drawdown if best_iteration else None),
                "bestSharpe": _metric_to_float(agent_task.best_sharpe),
            }

    return {
        "taskId": log.task_id,
        "entityType": entity_type,
        "entityId": entity_id,
        "name": task_name_from_log(log),
        "type": task_type_from_log(log),
        "status": task_status_from_log(log),
        "startedAt": started_at,
        "updatedAt": updated_at,
        "progressCurrent": progress_current,
        "progressTotal": progress_total,
        "progressText": log.message,
        "recordsAffected": log.records_affected,
        "durationMs": log.duration_ms,
        "logs": logs,
        **agent_payload,
    }


def task_name_from_log(log: EventLog) -> str:
    event_name = log.event_name or ""
    target = log.target or ""
    event_type = (log.event_type or "").lower()

    if "agent" in event_type:
        return log.source or "AI Agent 任务"

    if target and (event_name == "enqueue_sync_task" or event_name.startswith("sync_")):
        return f"{sync_item_label(target)}同步"
    return event_name_label(event_name) if event_name else "任务"


def task_type_from_log(log: EventLog) -> str:
    event_type = (log.event_type or "").lower()
    if "agent" in event_type:
        return "agent"
    return "sync"


def task_status_from_log(log: EventLog) -> str:
    status = (log.status or "").lower()
    if status in {"queued", "running", "success", "failure", "stopped"}:
        return status
    if status == "failed":
        return "failure"
    if status == "partial_success":
        return "success"
    return "queued"


def best_iteration_for_agent(agent_task: AgentTask) -> AgentIteration | None:
    query = AgentIteration.query.filter(AgentIteration.task_id == agent_task.id)
    if agent_task.best_annual_return is not None:
        query = query.filter(AgentIteration.annual_return == agent_task.best_annual_return)
    return query.order_by(AgentIteration.iteration_number.desc(), AgentIteration.id.desc()).first()


def _metric_to_float(value) -> float | None:
    return round(float(value), 2) if value is not None else None
