from __future__ import annotations

from decimal import Decimal

from sqlalchemy import desc, func

from app.extensions import db
from app.models.agent_task import AgentTask
from app.models.event_log import EventLog
from app.models.index_asset import IndexAsset
from app.models.index_daily_bar import IndexDailyBar
from app.models.stock import Stock
from app.models.stock_daily_bar import StockDailyBar
from app.models.strategy import Strategy
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
    best_strategy = (
        Strategy.query.filter(
            Strategy.user_id == user.id,
            Strategy.archived_at.is_(None),
            Strategy.annual_return.isnot(None),
        )
        .order_by(desc(Strategy.annual_return), desc(Strategy.updated_at), desc(Strategy.id))
        .first()
    )

    return {
        "metrics": {
            "syncedAssetCount": _synced_asset_count(),
            "strategyCount": strategy_count,
            "bestAnnualReturn": _format_percent(best_strategy.annual_return if best_strategy else None),
            "agentTaskCount": agent_count,
            "runningAgentTaskCount": running_agent_count,
        },
        "ranking": _list_strategy_ranking(user),
        "agentTasks": _list_running_agent_tasks(user),
        "syncStatus": _list_sync_status(),
        "recentBacktests": _list_recent_backtests(user),
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


def _list_strategy_ranking(user: User) -> list[dict]:
    rows = (
        Strategy.query.filter(
            Strategy.user_id == user.id,
            Strategy.archived_at.is_(None),
            Strategy.annual_return.isnot(None),
        )
        .order_by(desc(Strategy.annual_return), desc(Strategy.updated_at), desc(Strategy.id))
        .limit(8)
        .all()
    )
    return [
        {
            "id": row.id,
            "rank": index + 1,
            "name": row.name,
            "type": row.type,
            "source": row.source,
            "annualReturn": _format_percent(row.annual_return),
            "drawdown": _format_percent(row.max_drawdown),
            "status": row.status,
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


def _list_recent_backtests(user: User) -> list[dict]:
    rows = (
        Strategy.query.filter(
            Strategy.user_id == user.id,
            Strategy.annual_return.isnot(None),
        )
        .order_by(desc(Strategy.updated_at), desc(Strategy.id))
        .limit(6)
        .all()
    )
    return [
        {
            "id": row.id,
            "name": row.name,
            "annualReturn": _format_percent(row.annual_return),
            "drawdown": _format_percent(row.max_drawdown),
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


def _decimal_to_float(value: Decimal | None) -> float:
    return float(value) if value is not None else 0.0
