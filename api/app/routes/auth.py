from functools import wraps

from flask import Blueprint, g, request

from app.models.user import User
from app.services.auth_service import AuthError, authenticate_user, register_user
from app.utils.jwt import decode_access_token

auth_bp = Blueprint("auth", __name__)


def auth_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return {"message": "未提供有效的访问令牌。"}, 401

        token = header.removeprefix("Bearer ").strip()
        try:
            payload = decode_access_token(token)
        except Exception:
            return {"message": "访问令牌无效或已过期。"}, 401

        user = User.query.get(int(payload["sub"]))
        if not user or not user.is_active:
            return {"message": "用户不存在或已被禁用。"}, 401

        g.current_user = user
        return view(*args, **kwargs)

    return wrapped


@auth_bp.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}

    try:
        user, token = register_user(
            email=data.get("email", ""),
            username=data.get("username", ""),
            password=data.get("password", ""),
        )
    except AuthError as exc:
        return {"message": str(exc)}, 400

    return {
        "access_token": token,
        "token_type": "Bearer",
        "user": user.to_dict(),
    }, 201


@auth_bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}

    try:
        user, token = authenticate_user(
            email=data.get("email", ""),
            password=data.get("password", ""),
        )
    except AuthError as exc:
        return {"message": str(exc)}, 401

    return {
        "access_token": token,
        "token_type": "Bearer",
        "user": user.to_dict(),
    }


@auth_bp.post("/auth/logout")
def logout():
    return {}, 204


@auth_bp.get("/auth/me")
@auth_required
def me():
    return {"user": g.current_user.to_dict()}

