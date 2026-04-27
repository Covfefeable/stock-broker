from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.models.strategy_evaluation import StrategyEvaluation
from app.services.backtest_lab.ai import generate_evaluation_ai_advice
from app.services.backtest_lab.errors import BacktestLabError
from app.services.backtest_lab.evaluation import run_target_evaluation
from app.services.backtest_lab.scoring import calculate_evaluation_score, group_conclusion, summarize_result_group, summarize_trade_health
from app.services.backtest_lab.serialization import build_strategy_evaluation_report
from app.services.backtest_lab.target_selection import select_time_ranges
from app.services.data_center import log_event
from app.services.settings import get_performance_score_weights


def run_strategy_evaluation(evaluation: StrategyEvaluation, *, task_id: str | None = None) -> dict:
    strategy = evaluation.strategy
    if not strategy:
        raise BacktestLabError("评估任务缺少策略。")

    started_at = datetime.now(timezone.utc)
    evaluation.status = "running"
    evaluation.celery_task_id = task_id or evaluation.celery_task_id
    evaluation.started_at = started_at
    evaluation.updated_at = started_at
    db.session.commit()
    log_event(
        user=evaluation.user,
        task_id=task_id,
        event_type="backtest",
        event_name="strategy_evaluation_running",
        source=strategy.name,
        target=strategy.asset_name or strategy.asset_identifier,
        status="running",
        level="info",
        message=f"{strategy.name} 开始全面评估：跨标的、跨时间区间与交易健康度。",
    )

    report = build_strategy_evaluation_report(strategy, evaluation.id, evaluation.report or {})
    score = Decimal(str(report["score"]))
    evaluation.status = "success"
    evaluation.score = score
    evaluation.conclusion = report["conclusion"]
    evaluation.generality_conclusion = report["generality"]["conclusion"]
    evaluation.stability_conclusion = report["stability"]["conclusion"]
    evaluation.risk_conclusion = report["tradeHealth"]["conclusion"]
    evaluation.summary = report["summary"]
    evaluation.report = report
    evaluation.error_message = None
    evaluation.finished_at = datetime.now(timezone.utc)
    evaluation.updated_at = evaluation.finished_at
    db.session.commit()

    log_event(
        user=evaluation.user,
        task_id=task_id,
        event_type="backtest",
        event_name="strategy_evaluation_finished",
        source=strategy.name,
        target=strategy.asset_name or strategy.asset_identifier,
        status="success",
        level="info",
        message=f"{strategy.name} 全面评估完成，综合评分 {report['score']:.2f}，结论：{report['conclusion']}。",
    )
    return {"evaluationId": evaluation.id, "score": report["score"], "conclusion": report["conclusion"]}


def mark_strategy_evaluation_failed(evaluation: StrategyEvaluation, message: str, *, task_id: str | None = None) -> None:
    evaluation.status = "failure"
    evaluation.error_message = message
    evaluation.finished_at = datetime.now(timezone.utc)
    evaluation.updated_at = evaluation.finished_at
    db.session.commit()
    log_event(
        user=evaluation.user,
        task_id=task_id or evaluation.celery_task_id,
        event_type="backtest",
        event_name="strategy_evaluation_failed",
        source=evaluation.strategy.name if evaluation.strategy else "策略评估",
        target=evaluation.strategy.asset_name if evaluation.strategy else None,
        status="failed",
        level="error",
        message=message,
    )
