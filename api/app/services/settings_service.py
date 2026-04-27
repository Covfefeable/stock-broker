from app.extensions import db
from app.models.setting import Setting, default_ai_models
from app.models.user import User
from app.services.ai_client import AIClientError, call_chat_completion_content
from app.services.performance_score import (
    default_performance_score_weights,
    normalize_performance_score_weights,
)


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
    scoring = payload.get("scoring") or {}

    settings.canghai_api_key = (data_source.get("canghaiApiKey") or "").strip() or None
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


def test_ai_model_config(model_config: object) -> str:
    config = normalize_single_ai_model(model_config)
    try:
        return call_chat_completion_content(
            config,
            [
                {
                    "role": "system",
                    "content": "You are a connection test endpoint. Reply with one short hello sentence.",
                },
                {"role": "user", "content": "hello"},
            ],
            timeout=30,
            temperature=0,
        )
    except AIClientError as exc:
        raise SettingsError(str(exc)) from exc


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


def normalize_single_ai_model(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise SettingsError("AI 模型配置无效。")
    config = {
        "name": str(value.get("name", "")).strip(),
        "model": str(value.get("model", "")).strip(),
        "baseUrl": str(value.get("baseUrl", "")).strip(),
        "apiKey": str(value.get("apiKey", "")).strip(),
    }
    if not config["model"]:
        raise SettingsError("请填写模型名称。")
    if not config["baseUrl"]:
        raise SettingsError("请填写 Base URL。")
    if not config["apiKey"]:
        raise SettingsError("请填写 API Key。")
    return config
