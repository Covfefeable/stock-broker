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

