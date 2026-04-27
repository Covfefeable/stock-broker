from app.models.agent_task import AgentTask
from app.models.event_log import EventLog
from app.services.event_logs import event_name_label, sync_item_label
from app.services.task_center.agent_metrics import best_iteration_for_agent, metric_to_float


def build_task_summary(log: EventLog, logs: list[str]) -> dict:
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
                "bestAnnualReturn": metric_to_float(agent_task.best_annual_return),
                "bestMaxDrawdown": metric_to_float(
                    best_iteration.max_drawdown if best_iteration else None
                ),
                "bestSharpe": metric_to_float(agent_task.best_sharpe),
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
    if "backtest" in event_type:
        return log.source or "策略评估"

    if target and (event_name == "enqueue_sync_task" or event_name.startswith("sync_")):
        return f"{sync_item_label(target)}同步"
    return event_name_label(event_name) if event_name else "任务"


def task_type_from_log(log: EventLog) -> str:
    event_type = (log.event_type or "").lower()
    if "agent" in event_type:
        return "agent"
    if "backtest" in event_type:
        return "backtest"
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
