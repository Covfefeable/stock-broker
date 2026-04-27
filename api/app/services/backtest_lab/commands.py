from __future__ import annotations

from datetime import datetime, timezone

from app.extensions import db
from app.models.strategy import Strategy
from app.models.strategy_evaluation import StrategyEvaluation
from app.models.user import User
from app.services.backtest_lab.errors import BacktestLabError
from app.services.backtest_lab.target_selection import resolve_selected_cross_asset_targets, select_cross_asset_targets_for_auto
from app.services.data_center_service import log_event


def evaluate_strategy(user: User, strategy_id: int, selected_asset_identifiers: list[str] | None = None) -> StrategyEvaluation:
    strategy = Strategy.query.filter(Strategy.id == strategy_id, Strategy.user_id == user.id).first()
    if not strategy:
        raise BacktestLabError("未找到对应的策略。")
    if not strategy.asset_type or not strategy.asset_identifier:
        raise BacktestLabError("策略缺少原始标的信息，无法执行全面评估。")

    if selected_asset_identifiers is None:
        cross_asset_targets, selection_meta = select_cross_asset_targets_for_auto(user, strategy)
    else:
        cross_asset_targets = resolve_selected_cross_asset_targets(strategy, selected_asset_identifiers)
        selection_meta = {"mode": "manual", "message": "使用用户手动选择的跨标的样本。"}

    now = datetime.now(timezone.utc)
    evaluation = StrategyEvaluation.query.filter_by(user_id=user.id, strategy_id=strategy.id).first()
    if not evaluation:
        evaluation = StrategyEvaluation(user_id=user.id, strategy_id=strategy.id)
        db.session.add(evaluation)

    evaluation.status = "queued"
    evaluation.score = None
    evaluation.conclusion = None
    evaluation.generality_conclusion = None
    evaluation.stability_conclusion = None
    evaluation.risk_conclusion = None
    evaluation.summary = None
    evaluation.error_message = None
    evaluation.report = {
        "crossAssetSelection": selection_meta,
        "selectedCrossAssetTargets": cross_asset_targets,
    }
    evaluation.strategy_snapshot = strategy.to_dict()
    evaluation.started_at = None
    evaluation.finished_at = None
    evaluation.updated_at = now
    db.session.commit()

    from app.tasks.backtest_lab import run_strategy_evaluation_task

    async_result = run_strategy_evaluation_task.delay(evaluation_id=evaluation.id, user_id=user.id)
    evaluation.celery_task_id = async_result.id
    evaluation.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_event(
        user=user,
        task_id=async_result.id,
        event_type="backtest",
        event_name="strategy_evaluation_enqueued",
        source=strategy.name,
        target=strategy.asset_name or strategy.asset_identifier,
        status="queued",
        level="info",
        message=f"{strategy.name} 的全面评估任务已提交。",
    )
    return evaluation
