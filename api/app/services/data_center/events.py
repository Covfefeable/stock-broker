from datetime import datetime, timezone
from time import perf_counter


from app.extensions import db
from app.models.event_log import EventLog
from app.models.user import User
from app.services.task_center import publish_task_event

from app.services.data_center.constants import *  # noqa: F403
from app.services.data_center.errors import DataSyncError


def log_event(
    *,
    user: User | None,
    task_id: str | None = None,
    show_in_ui: bool = True,
    event_type: str,
    event_name: str,
    source: str | None,
    target: str | None,
    status: str,
    level: str,
    message: str,
    http_status: int | None = None,
    records_affected: int | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    duration_ms: int | None = None,
) -> EventLog:
    log = EventLog(
        user=user,
        task_id=task_id,
        show_in_ui=show_in_ui,
        event_type=event_type,
        event_name=event_name,
        source=source,
        target=target,
        status=status,
        level=level,
        message=message,
        http_status=http_status,
        records_affected=records_affected,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
    )
    db.session.add(log)
    db.session.commit()
    publish_task_event(log)
    return log


def raise_and_log_sync_error(
    *,
    user: User,
    task_id: str | None = None,
    sync_item: str,
    event_name: str,
    started_at: datetime,
    started_perf: float,
    message: str,
    http_status: int | None = None,
) -> None:
    finished_at = datetime.now(timezone.utc)
    duration_ms = int((perf_counter() - started_perf) * 1000)
    log_event(
        user=user,
        task_id=task_id,
        event_type="data_sync",
        event_name=event_name,
        source="canghai",
        target=sync_item,
        status="failed",
        level="error",
        message=message,
        http_status=http_status,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
    )
    raise DataSyncError(message)
