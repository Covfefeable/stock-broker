import json

from flask import Blueprint, g, request

from app.extensions import db, sock
from app.models.user import User
from app.routes.auth import auth_required
from app.services.task_center_service import (
    iter_task_events,
    list_recent_task_summaries,
    subscribe_task_events,
)
from app.utils.jwt import decode_access_token

task_center_bp = Blueprint("task_center", __name__)


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
        ws.send(json.dumps({"type": "error", "message": "访问令牌无效或已过期。"}, ensure_ascii=False))
        ws.close()
        return

    if not user or not user.is_active:
        ws.send(json.dumps({"type": "error", "message": "用户不存在或已被禁用。"}, ensure_ascii=False))
        ws.close()
        return

    user_id = user.id
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
        for message in iter_task_events(pubsub):
            payload = json.loads(message)
            if payload.get("userId") not in {None, user_id}:
                continue
            ws.send(json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass
    finally:
        pubsub.close()
        db.session.remove()
