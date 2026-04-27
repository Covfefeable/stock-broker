from app.models.event_log import EventLog
from app.services.event_logs.metadata import (
    EVENT_NAME_META,
    EVENT_TYPE_META,
    event_name_label,
    event_type_label,
    sync_item_label,
)


def event_log_to_dict(row: EventLog) -> dict:
    payload = row.to_dict()
    event_type_meta = EVENT_TYPE_META.get(row.event_type, {})
    event_name_meta = EVENT_NAME_META.get(row.event_name, {})
    payload["eventCategory"] = event_name_meta.get("category") or event_type_meta.get("category") or row.event_type
    payload["eventTypeLabel"] = event_type_label(row.event_type)
    payload["eventNameLabel"] = event_name_label(row.event_name)
    payload["targetLabel"] = sync_item_label(row.target) if row.target else None
    return payload
