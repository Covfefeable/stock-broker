import json
import time

from flask import Blueprint, g, request
from simple_websocket.errors import ConnectionClosed

from app.extensions import db, sock
from app.models.user import User
from app.routes.auth import auth_required
from app.services.task_center import (
    create_online_connection,
    list_recent_task_summaries,
    refresh_online_connection,
    subscribe_task_events,
)
from app.utils.jwt import decode_access_token

task_center_bp = Blueprint("task_center", __name__)

HEARTBEAT_TIMEOUT_SECONDS = 95
SOCKET_RECEIVE_TIMEOUT_SECONDS = 0.1
PUBSUB_POLL_SECONDS = 0.5


@task_center_bp.get("/task-center/tasks")
@auth_required
def list_tasks():
    return {"items": list_recent_task_summaries(user_id=g.current_user.id)}


@sock.route("/ws/tasks")
def task_stream(ws):
    token = str(request.args.get("token") or "").strip()
    if not token:
        ws.send(json.dumps({"type": "error", "message": "未提供访问令牌。"}, ensure_ascii=False))
        ws.close()
        return

    user_id: int
    try:
        payload = decode_access_token(token)
        user = User.query.get(int(payload["sub"]))
    except Exception:
        ws.send(
            json.dumps({"type": "error", "message": "访问令牌无效或已过期。"}, ensure_ascii=False)
        )
        ws.close()
        return

    if not user or not user.is_active:
        ws.send(
            json.dumps({"type": "error", "message": "用户不存在或已被禁用。"}, ensure_ascii=False)
        )
        ws.close()
        return

    user_id = user.id
    connection_id = create_online_connection(user_id)
    ws.send(
        json.dumps(
            {
                "type": "snapshot",
                "payload": {
                    "tasks": list_recent_task_summaries(user_id=user_id),
                },
            },
            ensure_ascii=False,
        )
    )
    db.session.remove()

    pubsub = subscribe_task_events()
    try:
        last_heartbeat_at = time.monotonic()
        while True:
            if _receive_heartbeat(ws):
                refresh_online_connection(user_id, connection_id)
                last_heartbeat_at = time.monotonic()

            message = pubsub.get_message(timeout=PUBSUB_POLL_SECONDS)
            if message and message.get("data"):
                payload = json.loads(message["data"])
                if payload.get("userId") in {None, user_id}:
                    ws.send(json.dumps(payload, ensure_ascii=False))
                    refresh_online_connection(user_id, connection_id)

            if time.monotonic() - last_heartbeat_at > HEARTBEAT_TIMEOUT_SECONDS:
                break
    except (ConnectionClosed, TimeoutError):
        pass
    finally:
        pubsub.close()
        db.session.remove()


def _receive_heartbeat(ws) -> bool:
    try:
        raw_message = ws.receive(timeout=SOCKET_RECEIVE_TIMEOUT_SECONDS)
    except TimeoutError:
        return False

    if not raw_message:
        return False

    if isinstance(raw_message, bytes):
        raw_message = raw_message.decode("utf-8")

    try:
        payload = json.loads(raw_message)
    except (TypeError, json.JSONDecodeError):
        return False

    return payload.get("type") == "heartbeat"
