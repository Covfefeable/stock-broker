from flask import Blueprint, g, request

from app.routes.auth import auth_required
from app.services.agent_task_service import (
    AgentTaskError,
    create_agent_task,
    delete_agent_task,
    get_agent_task_asset_options,
    get_agent_task_detail,
    preview_agent_iteration,
    list_available_ai_models,
    list_agent_tasks,
    request_stop_agent_task,
    rerun_agent_task,
)

agent_task_bp = Blueprint("agent_task", __name__)


@agent_task_bp.get("/agent-tasks")
@auth_required
def get_agent_tasks():
    page = max(request.args.get("page", default=1, type=int), 1)
    page_size = max(request.args.get("pageSize", default=10, type=int), 1)
    payload = list_agent_tasks(
        g.current_user,
        keyword=request.args.get("keyword", default="", type=str),
        country_code=request.args.get("countryCode", default="", type=str),
        asset_type=request.args.get("assetType", default="", type=str),
        status=request.args.get("status", default="", type=str),
        page=page,
        page_size=page_size,
    )
    return payload


@agent_task_bp.post("/agent-tasks")
@auth_required
def post_agent_task():
    payload = request.get_json(silent=True) or {}
    try:
        task = create_agent_task(g.current_user, payload)
    except AgentTaskError as exc:
        return {"message": str(exc)}, 400
    return {"message": "Agent 任务已创建。", "task": task.to_dict()}, 201


@agent_task_bp.get("/agent-tasks/<int:task_id>")
@auth_required
def get_agent_task_route(task_id: int):
    try:
        payload = get_agent_task_detail(g.current_user, task_id)
    except AgentTaskError as exc:
        return {"message": str(exc)}, 404
    return payload


@agent_task_bp.delete("/agent-tasks/<int:task_id>")
@auth_required
def delete_agent_task_route(task_id: int):
    try:
        delete_agent_task(g.current_user, task_id)
    except AgentTaskError as exc:
        return {"message": str(exc)}, 404
    return {}, 204


@agent_task_bp.post("/agent-tasks/<int:task_id>/rerun")
@auth_required
def rerun_agent_task_route(task_id: int):
    try:
        task = rerun_agent_task(g.current_user, task_id)
    except AgentTaskError as exc:
        return {"message": str(exc)}, 400
    return {"message": "Agent 任务已重新运行，原任务数据已保留。", "task": task.to_dict()}, 201


@agent_task_bp.post("/agent-tasks/<int:task_id>/stop")
@auth_required
def stop_agent_task_route(task_id: int):
    try:
        task = request_stop_agent_task(g.current_user, task_id)
    except AgentTaskError as exc:
        return {"message": str(exc)}, 400
    return {"message": "Agent 任务停止信号已发送。", "task": task.to_dict()}


@agent_task_bp.get("/agent-tasks/<int:task_id>/iterations/<int:iteration_id>/preview")
@auth_required
def preview_agent_iteration_route(task_id: int, iteration_id: int):
    try:
        payload = preview_agent_iteration(g.current_user, task_id, iteration_id)
    except AgentTaskError as exc:
        return {"message": str(exc)}, 400
    return payload


@agent_task_bp.get("/agent-tasks/asset-options")
@auth_required
def get_agent_task_asset_options_route():
    try:
        payload = get_agent_task_asset_options(
            request.args.get("countryCode", default="", type=str),
            request.args.get("assetType", default="", type=str),
        )
    except AgentTaskError as exc:
        return {"message": str(exc)}, 400
    return payload


@agent_task_bp.get("/agent-tasks/model-options")
@auth_required
def get_agent_task_model_options_route():
    return {"items": list_available_ai_models(g.current_user)}
