from sqlalchemy import desc

from app.extensions import db
from app.models.agent_task import AgentTask
from app.models.etf_daily_bar import EtfDailyBar
from app.models.index_daily_bar import IndexDailyBar
from app.models.stock_daily_bar import StockDailyBar
from app.models.strategy import Strategy
from app.models.strategy_evaluation import StrategyEvaluation
from app.models.user import User
from app.services.dashboard.formatters import format_score


def build_dashboard_metrics(user: User) -> dict:
    strategy_count = Strategy.query.filter(Strategy.user_id == user.id).count()
    agent_count = AgentTask.query.filter(AgentTask.user_id == user.id).count()
    running_agent_count = AgentTask.query.filter(
        AgentTask.user_id == user.id,
        AgentTask.status.in_(("queued", "running")),
    ).count()
    best_evaluation = (
        StrategyEvaluation.query.join(Strategy, Strategy.id == StrategyEvaluation.strategy_id)
        .filter(
            StrategyEvaluation.user_id == user.id,
            StrategyEvaluation.score.isnot(None),
            Strategy.archived_at.is_(None),
        )
        .order_by(
            desc(StrategyEvaluation.score),
            desc(StrategyEvaluation.updated_at),
            desc(StrategyEvaluation.id),
        )
        .first()
    )

    return {
        "syncedAssetCount": synced_asset_count(),
        "strategyCount": strategy_count,
        "bestScore": format_score(best_evaluation.score if best_evaluation else None),
        "agentTaskCount": agent_count,
        "runningAgentTaskCount": running_agent_count,
    }


def synced_asset_count() -> int:
    stock_count = (
        db.session.query(
            StockDailyBar.exchange_code,
            StockDailyBar.ticker,
        )
        .distinct()
        .count()
    )
    index_count = (
        db.session.query(
            IndexDailyBar.country_code,
            IndexDailyBar.ticker,
        )
        .distinct()
        .count()
    )
    etf_count = (
        db.session.query(
            EtfDailyBar.exchange_code,
            EtfDailyBar.ticker,
        )
        .distinct()
        .count()
    )
    return int(stock_count or 0) + int(etf_count or 0) + int(index_count or 0)
