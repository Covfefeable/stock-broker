from flask import Blueprint, g, request

from app.routes.auth import auth_required
from app.services.trade_decisions import (
    TradeDecisionError,
    evaluate_trade_decision,
    list_eligible_extra_strategies,
)

trade_decision_bp = Blueprint("trade_decision", __name__)


@trade_decision_bp.post("/trade-decisions/evaluate")
@auth_required
def post_trade_decision_evaluate():
    payload = request.get_json(silent=True) or {}
    try:
        return evaluate_trade_decision(g.current_user, payload)
    except TradeDecisionError as exc:
        return {"message": str(exc)}, 400


@trade_decision_bp.get("/trade-decisions/strategy-options")
@auth_required
def get_trade_decision_strategy_options():
    return list_eligible_extra_strategies(
        g.current_user,
        keyword=request.args.get("keyword", default="", type=str),
        exclude_asset_type=request.args.get("assetType", default="", type=str),
        exclude_asset_identifier=request.args.get("assetIdentifier", default="", type=str),
    )
