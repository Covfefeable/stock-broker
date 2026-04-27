from __future__ import annotations

from decimal import Decimal

from sqlalchemy import desc

from app.extensions import db
from app.models.agent_task import AgentTask
from app.models.event_log import EventLog
from app.models.index_asset import IndexAsset
from app.models.index_daily_bar import IndexDailyBar
from app.models.stock import Stock
from app.models.stock_daily_bar import StockDailyBar
from app.models.strategy import Strategy
from app.models.strategy_evaluation import StrategyEvaluation
from app.models.user import User
from app.services.event_log_meta import event_name_label, sync_item_label


def get_dashboard_overview(user: User) -> dict:
    strategy_count = Strategy.query.filter(Strategy.user_id == user.id).count()
    agent_count = AgentTask.query.filter(AgentTask.user_id == user.id).count()
    running_agent_count = (
        AgentTask.query.filter(
            AgentTask.user_id == user.id,
            AgentTask.status.in_(("queued", "running")),
        ).count()
    )
    best_evaluation = (
        StrategyEvaluation.query.join(Strategy, Strategy.id == StrategyEvaluation.strategy_id)
        .filter(
            StrategyEvaluation.user_id == user.id,
            StrategyEvaluation.score.isnot(None),
            Strategy.archived_at.is_(None),
        )
        .order_by(desc(StrategyEvaluation.score), desc(StrategyEvaluation.updated_at), desc(StrategyEvaluation.id))
        .first()
    )

    return {
        "metrics": {
            "syncedAssetCount": _synced_asset_count(),
            "strategyCount": strategy_count,
            "bestScore": _format_score(best_evaluation.score if best_evaluation else None),
            "agentTaskCount": agent_count,
            "runningAgentTaskCount": running_agent_count,
        },
        "ranking": _list_backtest_ranking(user),
        "agentTasks": _list_running_agent_tasks(user),
        "syncStatus": _list_sync_status(),
        "recentStrategies": _list_recent_strategies(user),
        "strategyAlerts": _list_strategy_alerts(user),
    }


def _synced_asset_count() -> int:
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
    return int(stock_count or 0) + int(index_count or 0)


def _list_backtest_ranking(user: User) -> list[dict]:
    rows = (
        StrategyEvaluation.query.join(Strategy, Strategy.id == StrategyEvaluation.strategy_id)
        .filter(
            StrategyEvaluation.user_id == user.id,
            StrategyEvaluation.score.isnot(None),
            Strategy.archived_at.is_(None),
        )
        .order_by(desc(StrategyEvaluation.score), desc(StrategyEvaluation.updated_at), desc(StrategyEvaluation.id))
        .limit(5)
        .all()
    )
    return [
        {
            "id": row.strategy_id,
            "rank": index + 1,
            "name": row.strategy.name if row.strategy else "-",
            "type": row.strategy.type if row.strategy else "-",
            "source": row.strategy.source if row.strategy else "-",
            "score": _format_score(row.score),
            "conclusion": row.conclusion,
            "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
        }
        for index, row in enumerate(rows)
    ]


def _list_running_agent_tasks(user: User) -> list[dict]:
    rows = (
        AgentTask.query.filter(
            AgentTask.user_id == user.id,
            AgentTask.status.in_(("queued", "running")),
        )
        .order_by(desc(AgentTask.updated_at), desc(AgentTask.id))
        .limit(5)
        .all()
    )
    return [
        {
            "id": row.id,
            "name": row.name,
            "status": row.status,
            "currentIteration": row.current_iteration,
            "maxIterations": row.max_iterations,
            "bestAnnualReturn": _format_percent(row.best_annual_return),
            "targetAnnualReturn": _format_percent(row.target_annual_return),
        }
        for row in rows
    ]


def _list_sync_status() -> list[dict]:
    targets = [
        "stock_list",
        "index_list",
        "stock_daily_history",
        "index_daily_history",
    ]
    return [
        {
            "target": target,
            "name": sync_item_label(target),
            "status": _sync_target_status(target),
            "latestEvent": _latest_sync_event(target),
        }
        for target in targets
    ]


def _latest_sync_event(target: str) -> dict | None:
    row = (
        EventLog.query.filter(
            EventLog.target == target,
            EventLog.event_type.in_(("data_sync", "data_sync_batch")),
            EventLog.show_in_ui.is_(True),
        )
        .order_by(desc(EventLog.created_at), desc(EventLog.id))
        .first()
    )
    if not row:
        return None
    return {
        "name": event_name_label(row.event_name),
        "status": row.status,
        "message": row.message,
        "time": row.created_at.isoformat() if row.created_at else None,
    }


def _sync_target_status(target: str) -> str:
    if target == "stock_list":
        return "success" if Stock.query.count() > 0 else "empty"
    if target == "index_list":
        return "success" if IndexAsset.query.count() > 0 else "empty"
    if target == "stock_daily_history":
        return "success" if StockDailyBar.query.count() > 0 else "empty"
    if target == "index_daily_history":
        return "success" if IndexDailyBar.query.count() > 0 else "empty"
    return "empty"


def _list_recent_strategies(user: User) -> list[dict]:
    rows = (
        Strategy.query.filter(
            Strategy.user_id == user.id,
            Strategy.archived_at.is_(None),
        )
        .order_by(desc(Strategy.updated_at), desc(Strategy.id))
        .limit(5)
        .all()
    )
    return [
        {
            "id": row.id,
            "name": row.name,
            "source": row.source,
            "status": row.status,
            "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in rows
    ]


def _list_strategy_alerts(user: User) -> list[dict]:
    rows = (
        Strategy.query.filter(
            Strategy.user_id == user.id,
            Strategy.archived_at.is_(None),
            Strategy.max_drawdown.isnot(None),
        )
        .order_by(desc(Strategy.max_drawdown), desc(Strategy.updated_at), desc(Strategy.id))
        .limit(3)
        .all()
    )
    return [
        {
            "id": row.id,
            "type": "回撤",
            "level": "warning" if _decimal_to_float(row.max_drawdown) < 30 else "danger",
            "message": f"{row.name} 最大回撤为 {_format_percent(row.max_drawdown)}",
        }
        for row in rows
    ]


def _format_percent(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{float(value):.2f}%"


def _format_score(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{float(value):.2f}"


def _decimal_to_float(value: Decimal | None) -> float:
    return float(value) if value is not None else 0.0
