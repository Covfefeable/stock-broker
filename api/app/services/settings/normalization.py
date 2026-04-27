from app.models.setting import default_ai_models
from app.services.settings.errors import SettingsError


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
