import json
import time

from app import extensions
from app.models.event_log import EventLog
from app.services.task_center.constants import TASK_CENTER_CHANNEL
from app.services.task_center.summary import build_task_summary


def publish_task_event(log: EventLog) -> None:
    if extensions.redis_client is None or not log.task_id or not log.show_in_ui:
        return

    payload = {
        "type": "task.updated",
        "userId": log.user_id,
        "payload": build_task_summary(log, [log.message] if log.message else []),
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
