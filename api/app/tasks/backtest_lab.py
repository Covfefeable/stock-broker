from celery import current_task
from celery.exceptions import SoftTimeLimitExceeded

from app.extensions import celery_app, db
from app.models.strategy_evaluation import StrategyEvaluation
from app.models.user import User
from app.services.backtest_lab import (
    BacktestLabError,
    mark_strategy_evaluation_failed,
    run_strategy_evaluation,
)


def _get_user(user_id: int) -> User:
    user = db.session.get(User, user_id)
    if not user:
        raise BacktestLabError(f"未找到用户 {user_id}，无法执行策略评估。")
    return user


def _get_evaluation(evaluation_id: int) -> StrategyEvaluation:
    evaluation = db.session.get(StrategyEvaluation, evaluation_id)
    if not evaluation:
        raise BacktestLabError(f"未找到策略评估任务 {evaluation_id}。")
    return evaluation


@celery_app.task(name="app.tasks.backtest_lab.run_strategy_evaluation_task")
def run_strategy_evaluation_task(*, evaluation_id: int, user_id: int) -> dict:
    _get_user(user_id)
    evaluation = _get_evaluation(evaluation_id)
    celery_task_id = current_task.request.id if current_task else None

    try:
        return run_strategy_evaluation(evaluation, task_id=celery_task_id)
    except SoftTimeLimitExceeded as exc:
        mark_strategy_evaluation_failed(evaluation, "策略全面评估执行超时。", task_id=celery_task_id)
        raise BacktestLabError("策略全面评估执行超时。") from exc
    except BacktestLabError as exc:
        mark_strategy_evaluation_failed(evaluation, str(exc), task_id=celery_task_id)
        raise
    except Exception as exc:
        mark_strategy_evaluation_failed(evaluation, f"策略全面评估执行失败：{exc}", task_id=celery_task_id)
        raise
