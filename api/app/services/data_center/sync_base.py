from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from time import perf_counter
from urllib.error import HTTPError, URLError


from app.models.user import User
from app.services.event_logs import sync_item_label

from app.services.data_center.constants import *  # noqa: F403
from app.services.data_center.canghai_client import build_canghai_url, fetch_json
from app.services.data_center.errors import DataSyncError
from app.services.data_center.events import log_event, raise_and_log_sync_error
from app.services.data_center.tokens import get_user_token


def sync_with_token_guard(
    *,
    user: User,
    task_id: str | None = None,
    sync_item: str,
    event_name: str,
    base_url: str,
    success_message: str,
    upsert_func,
    extra_params: dict[str, str] | None = None,
    log_result: bool = True,
) -> dict:
    started_at = datetime.now(timezone.utc)
    started_perf = perf_counter()

    try:
        token = get_user_token(user)
    except DataSyncError as exc:
        raise_and_log_sync_error(
            user=user,
            task_id=task_id,
            sync_item=sync_item,
            event_name=event_name,
            started_at=started_at,
            started_perf=started_perf,
            message=str(exc),
        )

    return sync_from_canghai(
        user=user,
        task_id=task_id,
        sync_item=sync_item,
        request_url=build_canghai_url(base_url, token, extra_params=extra_params),
        event_name=event_name,
        success_message=success_message,
        upsert_func=upsert_func,
        log_result=log_result,
    )


def sync_from_canghai(
    *,
    user: User,
    task_id: str | None = None,
    sync_item: str,
    request_url: str,
    event_name: str,
    success_message: str,
    upsert_func,
    log_result: bool = True,
) -> dict:
    started_at = datetime.now(timezone.utc)
    started_perf = perf_counter()

    try:
        payload = fetch_json(request_url)
        http_status = 200
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
        message = f"{sync_item_label(sync_item)}同步失败，请求返回 HTTP {exc.code}。"
        if body:
            message = f"{message} {body[:240]}"
        raise_and_log_sync_error(
            user=user,
            task_id=task_id,
            sync_item=sync_item,
            event_name=event_name,
            started_at=started_at,
            started_perf=started_perf,
            message=message,
            http_status=exc.code,
        )
    except URLError as exc:
        raise_and_log_sync_error(
            user=user,
            task_id=task_id,
            sync_item=sync_item,
            event_name=event_name,
            started_at=started_at,
            started_perf=started_perf,
            message=f"{sync_item_label(sync_item)}同步失败，网络请求异常：{exc.reason}",
        )

    code = payload.get("code")
    if code != 200:
        raise_and_log_sync_error(
            user=user,
            task_id=task_id,
            sync_item=sync_item,
            event_name=event_name,
            started_at=started_at,
            started_perf=started_perf,
            message=f"{sync_item_label(sync_item)}同步失败：{payload.get('msg') or '上游接口返回异常'}",
            http_status=http_status,
        )

    rows = payload.get("data") or []
    if not isinstance(rows, list):
        raise_and_log_sync_error(
            user=user,
            task_id=task_id,
            sync_item=sync_item,
            event_name=event_name,
            started_at=started_at,
            started_perf=started_perf,
            message=f"{sync_item_label(sync_item)}同步失败：上游接口返回的数据结构不符合预期。",
            http_status=http_status,
        )

    records_affected = upsert_func(rows)
    finished_at = datetime.now(timezone.utc)
    duration_ms = int((perf_counter() - started_perf) * 1000)

    if log_result:
        clean_success_message = success_message.rstrip("。.!?；; ")
        log_event(
            user=user,
            task_id=task_id,
            event_type="data_sync",
            event_name=event_name,
            source="canghai",
            target=sync_item,
            status="success",
            level="info",
            message=f"{clean_success_message}，共处理 {records_affected} 条记录。",
            http_status=http_status,
            records_affected=records_affected,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
        )

    return {
        "syncItem": sync_item,
        "syncItemLabel": sync_item_label(sync_item),
        "status": "success",
        "recordsAffected": records_affected,
        "durationMs": duration_ms,
        "finishedAt": finished_at.isoformat(),
    }


def normalize_optional_text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def parse_positive_decimal(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return decimal_value if decimal_value > 0 else None
