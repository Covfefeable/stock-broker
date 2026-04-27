from flask import Blueprint, g, request

from app.routes.auth import auth_required
from app.services.scheduled_plans import (
    ScheduledPlanError,
    create_scheduled_plan,
    delete_scheduled_plan,
    get_scheduled_plan_detail,
    list_agent_task_options,
    list_scheduled_plans,
    run_scheduled_plan_now,
    set_scheduled_plan_status,
    update_scheduled_plan,
)

scheduled_plan_bp = Blueprint("scheduled_plan", __name__)


@scheduled_plan_bp.get("/scheduled-plans")
@auth_required
def get_scheduled_plans():
    page = max(request.args.get("page", default=1, type=int), 1)
    page_size = max(request.args.get("pageSize", default=10, type=int), 1)
    return list_scheduled_plans(
        g.current_user,
        keyword=request.args.get("keyword", default="", type=str),
        status=request.args.get("status", default="", type=str),
        frequency_type=request.args.get("frequencyType", default="", type=str),
        page=page,
        page_size=page_size,
    )


@scheduled_plan_bp.get("/scheduled-plans/agent-options")
@auth_required
def get_scheduled_plan_agent_options():
    return list_agent_task_options(g.current_user)


@scheduled_plan_bp.post("/scheduled-plans")
@auth_required
def post_scheduled_plan():
    payload = request.get_json(silent=True) or {}
    try:
        plan = create_scheduled_plan(g.current_user, payload)
    except ScheduledPlanError as exc:
        return {"message": str(exc)}, 400
    return {"message": "计划任务已创建。", "plan": plan.to_dict()}, 201


@scheduled_plan_bp.get("/scheduled-plans/<int:plan_id>")
@auth_required
def get_scheduled_plan(plan_id: int):
    try:
        return get_scheduled_plan_detail(g.current_user, plan_id)
    except ScheduledPlanError as exc:
        return {"message": str(exc)}, 404


@scheduled_plan_bp.put("/scheduled-plans/<int:plan_id>")
@auth_required
def put_scheduled_plan(plan_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        plan = update_scheduled_plan(g.current_user, plan_id, payload)
    except ScheduledPlanError as exc:
        return {"message": str(exc)}, 400
    return {"message": "计划任务已更新。", "plan": plan.to_dict()}


@scheduled_plan_bp.delete("/scheduled-plans/<int:plan_id>")
@auth_required
def delete_scheduled_plan_route(plan_id: int):
    try:
        delete_scheduled_plan(g.current_user, plan_id)
    except ScheduledPlanError as exc:
        return {"message": str(exc)}, 404
    return {}, 204


@scheduled_plan_bp.post("/scheduled-plans/<int:plan_id>/enable")
@auth_required
def enable_scheduled_plan_route(plan_id: int):
    try:
        plan = set_scheduled_plan_status(g.current_user, plan_id, "enabled")
    except ScheduledPlanError as exc:
        return {"message": str(exc)}, 400
    return {"message": "计划任务已启用。", "plan": plan.to_dict()}


@scheduled_plan_bp.post("/scheduled-plans/<int:plan_id>/disable")
@auth_required
def disable_scheduled_plan_route(plan_id: int):
    try:
        plan = set_scheduled_plan_status(g.current_user, plan_id, "disabled")
    except ScheduledPlanError as exc:
        return {"message": str(exc)}, 400
    return {"message": "计划任务已停用。", "plan": plan.to_dict()}


@scheduled_plan_bp.post("/scheduled-plans/<int:plan_id>/run-now")
@auth_required
def run_scheduled_plan_now_route(plan_id: int):
    try:
        result = run_scheduled_plan_now(g.current_user, plan_id)
    except ScheduledPlanError as exc:
        return {"message": str(exc)}, 400
    return {"message": "计划任务已触发。", **result}, 202
