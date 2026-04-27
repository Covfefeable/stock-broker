from __future__ import annotations

from sqlalchemy import and_, asc, desc, nullslast, or_

from app.extensions import db
from app.models.strategy import Strategy
from app.models.strategy_evaluation import StrategyEvaluation
from app.models.user import User
from app.services.backtest_lab.errors import BacktestLabError
from app.services.backtest_lab.serialization import backtest_lab_strategy_to_dict


def list_backtest_lab_strategies(
    user: User,
    *,
    keyword: str = "",
    source: str = "",
    evaluation_status: str = "",
    sort_by: str = "",
    sort_order: str = "",
    page: int = 1,
    page_size: int = 10,
) -> dict:
    query = Strategy.query.filter(Strategy.user_id == user.id)
    evaluation_joined = False

    normalized_keyword = keyword.strip()
    if normalized_keyword:
        pattern = f"%{normalized_keyword}%"
        query = query.filter(or_(Strategy.name.ilike(pattern), Strategy.type.ilike(pattern), Strategy.source.ilike(pattern)))
    if source:
        query = query.filter(Strategy.source == source)

    if evaluation_status:
        if evaluation_status == "not_evaluated":
            query = query.outerjoin(StrategyEvaluation, StrategyEvaluation.strategy_id == Strategy.id).filter(
                StrategyEvaluation.id.is_(None)
            )
            evaluation_joined = True
        elif evaluation_status == "evaluating":
            query = query.join(StrategyEvaluation, StrategyEvaluation.strategy_id == Strategy.id).filter(
                StrategyEvaluation.user_id == user.id,
                StrategyEvaluation.status.in_(("queued", "running")),
            )
            evaluation_joined = True
        else:
            query = query.join(StrategyEvaluation, StrategyEvaluation.strategy_id == Strategy.id).filter(
                StrategyEvaluation.user_id == user.id,
                StrategyEvaluation.status == evaluation_status,
            )
            evaluation_joined = True

    if sort_by == "score":
        if not evaluation_joined:
            query = query.outerjoin(
                StrategyEvaluation,
                and_(StrategyEvaluation.strategy_id == Strategy.id, StrategyEvaluation.user_id == user.id),
            )
        direction = asc if sort_order == "asc" else desc
        query = query.order_by(nullslast(direction(StrategyEvaluation.score)), Strategy.updated_at.desc(), Strategy.id.desc())
    else:
        query = query.order_by(Strategy.updated_at.desc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    evaluations = {
        item.strategy_id: item
        for item in StrategyEvaluation.query.filter(
            StrategyEvaluation.user_id == user.id,
            StrategyEvaluation.strategy_id.in_([strategy.id for strategy in items] or [0]),
        ).all()
    }

    source_options = [
        value
        for value in db.session.query(Strategy.source)
        .filter(Strategy.user_id == user.id)
        .distinct()
        .order_by(Strategy.source.asc())
        .all()
    ]

    return {
        "items": [backtest_lab_strategy_to_dict(strategy, evaluations.get(strategy.id)) for strategy in items],
        "pagination": {"page": page, "pageSize": page_size, "total": total},
        "filters": {
            "sources": [value for (value,) in source_options if value],
            "evaluationStatuses": ["not_evaluated", "evaluating", "success", "failure"],
        },
    }


def get_strategy_evaluation_detail(user: User, strategy_id: int) -> dict:
    strategy = Strategy.query.filter(Strategy.id == strategy_id, Strategy.user_id == user.id).first()
    if not strategy:
        raise BacktestLabError("未找到对应的策略。")
    evaluation = StrategyEvaluation.query.filter_by(user_id=user.id, strategy_id=strategy.id).first()
    return {
        "strategy": backtest_lab_strategy_to_dict(strategy, evaluation),
        "evaluation": evaluation.to_dict() if evaluation else None,
    }
