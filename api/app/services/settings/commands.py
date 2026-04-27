from app.extensions import db
from app.models.setting import Setting
from app.models.user import User
from app.services.scoring import (
    default_performance_score_weights,
    normalize_performance_score_weights,
)
from app.services.settings.normalization import normalize_ai_models


def get_or_create_settings(user: User) -> Setting:
    if user.settings:
        return user.settings

    settings = Setting(user=user)
    db.session.add(settings)
    db.session.commit()
    return settings


def update_settings(user: User, payload: dict) -> Setting:
    settings = get_or_create_settings(user)

    data_source = payload.get("dataSource") or {}
    ai = payload.get("ai") or {}
    notifications = payload.get("notifications") or {}
    account = payload.get("account") or {}
    scoring = payload.get("scoring") or {}

    settings.canghai_api_key = (data_source.get("canghaiApiKey") or "").strip() or None
    settings.canghai_token_check_enabled = bool(
        data_source.get("canghaiTokenCheckEnabled", True)
    )
    settings.ai_models = normalize_ai_models(ai.get("models"))
    settings.performance_score_weights = normalize_performance_score_weights(
        scoring.get("performanceScoreWeights")
    )
    settings.notification_data_sync = bool(notifications.get("dataSync", False))
    settings.notification_agent_goal = bool(notifications.get("agentGoal", False))
    settings.notification_backtest = bool(notifications.get("backtest", False))
    settings.keep_signed_in = bool(account.get("keepSignedIn", True))

    db.session.commit()
    return settings


def get_performance_score_weights(user: User | None) -> dict[str, float]:
    if not user:
        return default_performance_score_weights()
    settings = get_or_create_settings(user)
    return normalize_performance_score_weights(settings.performance_score_weights)
