from flask import Blueprint, g, request

from app.routes.auth import auth_required
from app.services.strategies import (
    StrategyError,
    archive_strategy,
    create_strategy,
    get_strategy,
    delete_strategy,
    list_strategies,
    list_strategy_asset_options,
    preview_strategy,
    update_strategy,
)

strategy_bp = Blueprint("strategy", __name__)


@strategy_bp.get("/strategies")
@auth_required
def get_strategies():
    page = max(request.args.get("page", default=1, type=int), 1)
    page_size = max(request.args.get("pageSize", default=10, type=int), 1)
    payload = list_strategies(
        g.current_user,
        keyword=request.args.get("keyword", default="", type=str),
        country_region=request.args.get("countryRegion", default="", type=str),
        source=request.args.get("source", default="", type=str),
        status=request.args.get("status", default="", type=str),
        page=page,
        page_size=page_size,
        sort_field=request.args.get("sortField", default="updatedAt", type=str),
        sort_order=request.args.get("sortOrder", default="descend", type=str),
    )
    return payload


@strategy_bp.post("/strategies")
@auth_required
def post_strategy():
    payload = request.get_json(silent=True) or {}
    try:
        strategy = create_strategy(g.current_user, payload)
    except StrategyError as exc:
        return {"message": str(exc)}, 400

    evaluation = None
    evaluation_error = None
    try:
        from app.services.backtest_lab import evaluate_strategy

        evaluation = evaluate_strategy(g.current_user, strategy.id)
    except Exception as exc:  # noqa: BLE001
        evaluation_error = str(exc)

    return {
        "message": "策略基础信息已保存为草稿，已自动提交全面评估任务。" if evaluation else "策略基础信息已保存为草稿。",
        "strategy": strategy.to_dict(),
        "evaluation": evaluation.to_dict() if evaluation else None,
        "evaluationTaskId": evaluation.celery_task_id if evaluation else None,
        "evaluationError": evaluation_error,
    }, 201


@strategy_bp.post("/strategies/preview")
@auth_required
def post_strategy_preview():
    payload = request.get_json(silent=True) or {}
    try:
        preview = preview_strategy(g.current_user, payload)
    except StrategyError as exc:
        return {"message": str(exc)}, 400

    return {"message": "收益预览已更新。", "preview": preview}


@strategy_bp.get("/strategies/<int:strategy_id>")
@auth_required
def get_strategy_detail(strategy_id: int):
    try:
        strategy = get_strategy(g.current_user, strategy_id)
    except StrategyError as exc:
        return {"message": str(exc)}, 404

    return {"strategy": strategy.to_dict()}


@strategy_bp.put("/strategies/<int:strategy_id>")
@auth_required
def put_strategy(strategy_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        strategy = update_strategy(g.current_user, strategy_id, payload)
    except StrategyError as exc:
        return {"message": str(exc)}, 400

    return {
        "message": "策略已更新。",
        "strategy": strategy.to_dict(),
    }


@strategy_bp.get("/strategies/asset-options")
@auth_required
def get_strategy_asset_options():
    try:
        payload = list_strategy_asset_options(
            request.args.get("countryCode", default="", type=str),
            request.args.get("assetType", default="", type=str),
        )
    except StrategyError as exc:
        return {"message": str(exc)}, 400
    return payload


@strategy_bp.post("/strategies/<int:strategy_id>/archive")
@auth_required
def post_archive_strategy(strategy_id: int):
    try:
        strategy = archive_strategy(g.current_user, strategy_id)
    except StrategyError as exc:
        return {"message": str(exc)}, 404

    return {
        "message": "策略已归档。",
        "strategy": strategy.to_dict(),
    }


@strategy_bp.delete("/strategies/<int:strategy_id>")
@auth_required
def delete_strategy_route(strategy_id: int):
    try:
        delete_strategy(g.current_user, strategy_id)
    except StrategyError as exc:
        return {"message": str(exc)}, 404

    return {}, 204
