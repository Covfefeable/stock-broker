from collections import OrderedDict, defaultdict

from app.models.event_log import EventLog
from app.services.task_center.summary import build_task_summary


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
        items.append(build_task_summary(latest, list(reversed(log_map[task_id]))))
    return items
