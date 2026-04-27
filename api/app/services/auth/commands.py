from datetime import datetime, timezone

from app.extensions import db
from app.models.setting import Setting
from app.models.user import User
from app.services.auth.errors import AuthError
from app.utils.jwt import create_access_token
from app.utils.security import hash_password, is_valid_email, verify_password


def register_user(email: str, username: str, password: str) -> tuple[User, str]:
    normalized_email = email.strip().lower()
    normalized_username = username.strip()

    if not normalized_username:
        raise AuthError("用户名不能为空。")
    if not is_valid_email(normalized_email):
        raise AuthError("邮箱格式不正确。")
    if len(password) < 8:
        raise AuthError("密码长度至少为 8 位。")
    if User.query.filter_by(email=normalized_email).first():
        raise AuthError("该邮箱已注册。")

    user = User(
        email=normalized_email,
        username=normalized_username,
        password_hash=hash_password(password),
    )
    db.session.add(user)
    db.session.flush()
    db.session.add(Setting(user=user))
    db.session.commit()

    token = create_access_token(user.id, user.email)
    return user, token


def authenticate_user(email: str, password: str) -> tuple[User, str]:
    normalized_email = email.strip().lower()
    user = User.query.filter_by(email=normalized_email).first()

    if not user or not verify_password(user.password_hash, password):
        raise AuthError("邮箱或密码错误。")
    if not user.is_active:
        raise AuthError("账号已被禁用。")

    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()

    token = create_access_token(user.id, user.email)
    return user, token
