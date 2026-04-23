from app.extensions import db
from app.models.setting import Setting, default_ai_models
from app.models.user import User


class SettingsError(ValueError):
    pass


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

    settings.canghai_api_key = (data_source.get("canghaiApiKey") or "").strip() or None
    settings.ai_models = normalize_ai_models(ai.get("models"))
    settings.notification_data_sync = bool(notifications.get("dataSync", False))
    settings.notification_agent_goal = bool(notifications.get("agentGoal", False))
    settings.notification_backtest = bool(notifications.get("backtest", False))
    settings.keep_signed_in = bool(account.get("keepSignedIn", True))

    db.session.commit()
    return settings


def normalize_ai_models(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list) or len(value) == 0:
        return default_ai_models()

    normalized: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue

        normalized.append(
            {
                "name": str(item.get("name", "")).strip(),
                "model": str(item.get("model", "")).strip(),
                "baseUrl": str(item.get("baseUrl", "")).strip(),
                "apiKey": str(item.get("apiKey", "")).strip(),
            }
        )

    valid_rows = [row for row in normalized if any(row.values())]
    return valid_rows or default_ai_models()
