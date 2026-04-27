from flask import Blueprint, g, request

from app.routes.auth import auth_required
from app.services.backtest_lab import (
    BacktestLabError,
    evaluate_strategy,
    generate_improved_strategy,
    get_strategy_evaluation_detail,
    list_evaluation_candidate_assets,
    list_backtest_lab_strategies,
    select_candidate_assets_by_ai,
)

backtest_lab_bp = Blueprint("backtest_lab", __name__)


@backtest_lab_bp.get("/backtest-lab/strategies")
@auth_required
def get_backtest_lab_strategies():
    page = max(request.args.get("page", default=1, type=int), 1)
    page_size = max(request.args.get("pageSize", default=10, type=int), 1)
    return list_backtest_lab_strategies(
        g.current_user,
        keyword=request.args.get("keyword", default="", type=str),
        source=request.args.get("source", default="", type=str),
        evaluation_status=request.args.get("evaluationStatus", default="", type=str),
        sort_by=request.args.get("sortBy", default="", type=str),
        sort_order=request.args.get("sortOrder", default="", type=str),
        page=page,
        page_size=page_size,
    )


@backtest_lab_bp.get("/backtest-lab/strategies/<int:strategy_id>")
@auth_required
def get_backtest_lab_strategy_detail(strategy_id: int):
    try:
        return get_strategy_evaluation_detail(g.current_user, strategy_id)
    except BacktestLabError as exc:
        return {"message": str(exc)}, 404


@backtest_lab_bp.post("/backtest-lab/strategies/<int:strategy_id>/evaluate")
@auth_required
def post_evaluate_strategy(strategy_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        selected_asset_identifiers = payload.get("assetIdentifiers")
        if selected_asset_identifiers is not None and not isinstance(selected_asset_identifiers, list):
            return {"message": "评估标的参数格式无效。"}, 400
        evaluation = evaluate_strategy(g.current_user, strategy_id, selected_asset_identifiers)
    except BacktestLabError as exc:
        return {"message": str(exc)}, 400
    return {
        "message": "策略全面评估任务已提交。",
        "evaluation": evaluation.to_dict(),
        "taskId": evaluation.celery_task_id,
    }, 202


@backtest_lab_bp.post("/backtest-lab/strategies/<int:strategy_id>/generate-improved")
@auth_required
def post_generate_improved_strategy(strategy_id: int):
    try:
        draft = generate_improved_strategy(g.current_user, strategy_id)
    except BacktestLabError as exc:
        return {"message": str(exc)}, 400
    return {"message": "更优策略草稿已生成。", "draft": draft}


@backtest_lab_bp.get("/backtest-lab/strategies/<int:strategy_id>/candidate-assets")
@auth_required
def get_evaluation_candidate_assets(strategy_id: int):
    try:
        return list_evaluation_candidate_assets(g.current_user, strategy_id)
    except BacktestLabError as exc:
        return {"message": str(exc)}, 404


@backtest_lab_bp.post("/backtest-lab/strategies/<int:strategy_id>/candidate-assets/ai")
@auth_required
def post_select_candidate_assets_by_ai(strategy_id: int):
    try:
        return select_candidate_assets_by_ai(g.current_user, strategy_id)
    except BacktestLabError as exc:
        return {"message": str(exc)}, 400
