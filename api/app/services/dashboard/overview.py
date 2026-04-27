from app.models.user import User
from app.services.dashboard.metrics import build_dashboard_metrics
from app.services.dashboard.sections import (
    list_backtest_ranking,
    list_recent_strategies,
    list_running_agent_tasks,
    list_strategy_alerts,
    list_sync_status,
)


def get_dashboard_overview(user: User) -> dict:
    return {
        "metrics": build_dashboard_metrics(user),
        "ranking": list_backtest_ranking(user),
        "agentTasks": list_running_agent_tasks(user),
        "syncStatus": list_sync_status(),
        "recentStrategies": list_recent_strategies(user),
        "strategyAlerts": list_strategy_alerts(user),
    }
