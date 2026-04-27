import json
import os
from datetime import datetime, timedelta, timezone
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from app.extensions import db
from app.models.setting import Setting
from app.models.user import User
from app.models.user_data_source_status import UserDataSourceStatus
from app.services.data_center.canghai_client import build_canghai_url, canghai_stock_daily_url
from app.services.data_center.constants import CANGHAI_SOURCE_KEY, CANGHAI_SOURCE_NAME
from app.services.data_center.events import log_event
from app.services.settings.commands import get_or_create_settings
from app.services.settings.errors import SettingsError
from app.services.task_center import iter_online_user_ids

TOKEN_CHECK_INTERVAL_MINUTES = int(os.getenv("TOKEN_STATUS_CHECK_INTERVAL_MINUTES", "30"))


def get_canghai_token_status(user: User) -> dict:
    settings = get_or_create_settings(user)
    status = _get_or_create_status(user)
    return {
        "sourceKey": CANGHAI_SOURCE_KEY,
        "sourceName": CANGHAI_SOURCE_NAME,
        "scheduledCheckEnabled": settings.canghai_token_check_enabled,
        "status": status.to_dict(),
    }


def test_canghai_token_for_user(
    user: User,
    *,
    api_key: str | None = None,
    task_id: str | None = None,
) -> dict:
    settings = get_or_create_settings(user)
    token = (api_key if api_key is not None else settings.canghai_api_key or "").strip()
    if not token:
        raise SettingsError("未配置沧海数据 API Key，无法检测。")
    status = _check_canghai_token(user, token, task_id=task_id)
    return get_canghai_token_status(user) | {"checked": status.to_dict()}


def scan_online_canghai_token_statuses(*, task_id: str | None = None) -> dict:
    online_user_ids = iter_online_user_ids()
    if not online_user_ids:
        return {"scanned": 0, "checked": 0, "skipped": 0}

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=TOKEN_CHECK_INTERVAL_MINUTES)
    rows = (
        db.session.query(User, Setting)
        .join(Setting, Setting.user_id == User.id)
        .filter(User.id.in_(online_user_ids))
        .filter(User.is_active.is_(True))
        .filter(Setting.canghai_api_key.isnot(None), Setting.canghai_api_key != "")
        .filter(Setting.canghai_token_check_enabled.is_(True))
        .all()
    )

    checked = 0
    skipped = 0
    for user, settings in rows:
        status = _get_or_create_status(user)
        if status.last_checked_at and status.last_checked_at > cutoff:
            skipped += 1
            continue
        _check_canghai_token(user, settings.canghai_api_key.strip(), task_id=task_id)
        checked += 1

    return {"scanned": len(rows), "checked": checked, "skipped": skipped}


def _get_or_create_status(user: User) -> UserDataSourceStatus:
    status = UserDataSourceStatus.query.filter_by(
        user_id=user.id,
        source_key=CANGHAI_SOURCE_KEY,
    ).first()
    if status:
        return status

    status = UserDataSourceStatus(
        user_id=user.id,
        source_key=CANGHAI_SOURCE_KEY,
        source_name=CANGHAI_SOURCE_NAME,
        status="unknown",
        token_status="unknown",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.session.add(status)
    db.session.commit()
    return status


def _check_canghai_token(
    user: User,
    token: str,
    *,
    task_id: str | None = None,
) -> UserDataSourceStatus:
    started_at = datetime.now(timezone.utc)
    started_perf = perf_counter()
    http_status: int | None = None
    token_status = "error"
    status_value = "abnormal"
    message = "API Key 检测失败"

    try:
        check_date = datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Shanghai")).date() - timedelta(days=1)
        request_url = build_canghai_url(
            canghai_stock_daily_url("XNAS"),
            token,
            extra_params={
                "ticker": "TSLA",
                "start_date": check_date.isoformat(),
                "end_date": check_date.isoformat(),
            },
        )
        request = Request(
            request_url,
            headers={"Accept": "application/json", "User-Agent": "stock-broker/0.1"},
        )
        with urlopen(request, timeout=20) as response:
            http_status = response.status
            payload = json.loads(response.read().decode("utf-8"))
            code = int(payload.get("code") or 0)
            message = str(payload.get("msg") or "操作完成")
            if http_status == 200 and code == 200:
                token_status = "valid"
                status_value = "normal"
            else:
                token_status = _classify_token_failure(message, http_status)
    except HTTPError as exc:
        http_status = exc.code
        message = f"HTTP {exc.code}"
        token_status = _classify_token_failure(message, http_status)
    except URLError as exc:
        message = f"网络异常：{exc.reason}"
    except Exception as exc:
        message = f"检测异常：{exc}"

    checked_at = datetime.now(timezone.utc)
    latency_ms = int((perf_counter() - started_perf) * 1000)
    record = _get_or_create_status(user)
    record.status = status_value
    record.token_status = token_status
    record.last_checked_at = checked_at
    record.latency_ms = latency_ms
    record.http_status = http_status
    record.message = message[:255]
    if token_status == "valid":
        record.last_success_at = checked_at
        record.failure_count = 0
    else:
        record.last_failed_at = checked_at
        record.failure_count = (record.failure_count or 0) + 1
    db.session.commit()

    log_event(
        user=user,
        task_id=task_id,
        show_in_ui=False,
        event_type="data_source_api_key_check",
        event_name="canghai_api_key_check",
        source="canghai",
        target=CANGHAI_SOURCE_KEY,
        status="success" if token_status == "valid" else "failed",
        level="info" if token_status == "valid" else "warning",
        message=f"{CANGHAI_SOURCE_NAME} API Key 检测完成：{message}",
        http_status=http_status,
        started_at=started_at,
        finished_at=checked_at,
        duration_ms=latency_ms,
    )
    return record


def _classify_token_failure(message: str, http_status: int | None) -> str:
    if http_status in {401, 403}:
        return "invalid"
    normalized = message.lower()
    if "过期" in message or "expired" in normalized:
        return "expired"
    if any(text in normalized for text in ("token", "key", "auth")) or any(
        text in message for text in ("认证", "权限", "无效", "未授权")
    ):
        return "invalid"
    return "error"
