from flask import Blueprint, g, request

from app.routes.auth import auth_required
from app.services.settings_service import SettingsError, get_or_create_settings, test_ai_model_config, update_settings

settings_bp = Blueprint("settings", __name__)


@settings_bp.get("/settings/me")
@auth_required
def get_settings():
    settings = get_or_create_settings(g.current_user)
    return {"settings": settings.to_dict()}


@settings_bp.put("/settings/me")
@auth_required
def put_settings():
    payload = request.get_json(silent=True) or {}
    settings = update_settings(g.current_user, payload)
    return {"settings": settings.to_dict()}


@settings_bp.post("/settings/test-ai-model")
@auth_required
def test_ai_model():
    payload = request.get_json(silent=True) or {}
    try:
        content = test_ai_model_config(payload.get("modelConfig"))
    except SettingsError as exc:
        return {"message": str(exc)}, 400
    return {
        "ok": True,
        "message": "AI 模型测试成功",
        "content": content,
    }
