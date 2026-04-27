from app.extensions import db
from app.models.setting import Setting
from app.models.user import User
from app.services.settings import get_or_create_settings

from app.services.data_center.constants import *  # noqa: F403
from app.services.data_center.errors import DataSyncError


def get_user_token(user: User) -> str:
    settings = get_or_create_settings(user)
    token = (settings.canghai_api_key or "").strip()
    if token:
        return token
    raise DataSyncError("未配置沧海数据 API Key，无法执行同步。")


def get_any_canghai_token() -> str:
    row = (
        db.session.query(Setting.canghai_api_key)
        .filter(Setting.canghai_api_key.isnot(None), Setting.canghai_api_key != "")
        .order_by(Setting.updated_at.desc(), Setting.id.desc())
        .first()
    )
    token = (row[0] if row else "") or ""
    token = token.strip()
    if token:
        return token
    raise DataSyncError("未配置沧海数据 API Key，无法执行状态检测。")
