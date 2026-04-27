from flask import Blueprint, g, request

from app.routes.auth import auth_required
from app.services.settings import (
    SettingsError,
    get_canghai_token_status,
    get_or_create_settings,
    test_ai_model_config,
    test_canghai_token_for_user,
    update_settings,
)

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


@settings_bp.get("/settings/data-sources/canghai/status")
@auth_required
def get_canghai_status():
    return get_canghai_token_status(g.current_user)


@settings_bp.post("/settings/data-sources/canghai/test-token")
@auth_required
def test_canghai_token():
    payload = request.get_json(silent=True) or {}
    api_key = payload.get("apiKey")
    if api_key is not None:
        api_key = str(api_key)
    try:
        return test_canghai_token_for_user(g.current_user, api_key=api_key)
    except SettingsError as exc:
        return {"message": str(exc)}, 400
