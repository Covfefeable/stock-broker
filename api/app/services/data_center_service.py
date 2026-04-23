import json
from datetime import datetime, timezone
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy import select

from app.extensions import db
from app.models.country import Country
from app.models.event_log import EventLog
from app.models.exchange import Exchange
from app.models.user import User
from app.services.settings_service import get_or_create_settings

CANGHAI_COUNTRY_URL = "https://www.tsanghi.com/api/fin/index/country"
CANGHAI_EXCHANGE_URL = "https://www.tsanghi.com/api/fin/stock/exchange"
SYNC_ITEM_COUNTRY_LIST = "country_list"
SYNC_ITEM_EXCHANGE_LIST = "exchange_list"


class DataSyncError(ValueError):
    pass


def sync_item_label(sync_item: str) -> str:
    if sync_item == SYNC_ITEM_COUNTRY_LIST:
        return "国家/地区清单"
    if sync_item == SYNC_ITEM_EXCHANGE_LIST:
        return "交易所清单"
    return sync_item


def sync_country_list(user: User) -> dict:
    return sync_with_token_guard(
        user=user,
        sync_item=SYNC_ITEM_COUNTRY_LIST,
        event_name="sync_country_list",
        base_url=CANGHAI_COUNTRY_URL,
        success_message="国家/地区清单同步成功",
        upsert_func=upsert_countries,
    )


def sync_exchange_list(user: User) -> dict:
    return sync_with_token_guard(
        user=user,
        sync_item=SYNC_ITEM_EXCHANGE_LIST,
        event_name="sync_exchange_list",
        base_url=CANGHAI_EXCHANGE_URL,
        success_message="交易所清单同步成功",
        upsert_func=upsert_exchanges,
    )


def sync_with_token_guard(
    *,
    user: User,
    sync_item: str,
    event_name: str,
    base_url: str,
    success_message: str,
    upsert_func,
) -> dict:
    started_at = datetime.now(timezone.utc)
    started_perf = perf_counter()

    try:
        token = get_user_token(user)
    except DataSyncError as exc:
        raise_and_log_sync_error(
            user=user,
            sync_item=sync_item,
            event_name=event_name,
            started_at=started_at,
            started_perf=started_perf,
            message=str(exc),
        )

    return sync_from_canghai(
        user=user,
        sync_item=sync_item,
        request_url=build_canghai_url(base_url, token),
        event_name=event_name,
        success_message=success_message,
        upsert_func=upsert_func,
    )


def sync_from_canghai(
    *,
    user: User,
    sync_item: str,
    request_url: str,
    event_name: str,
    success_message: str,
    upsert_func,
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

    log_event(
        user=user,
        event_type="data_sync",
        event_name=event_name,
        source="canghai",
        target=sync_item,
        status="success",
        level="info",
        message=f"{success_message}，共处理 {records_affected} 条记录。",
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


def list_recent_event_logs(limit: int = 20) -> list[dict]:
    rows = (
        EventLog.query.order_by(EventLog.created_at.desc(), EventLog.id.desc())
        .limit(limit)
        .all()
    )
    return [row.to_dict() for row in rows]


def get_user_token(user: User) -> str:
    settings = get_or_create_settings(user)
    token = (settings.canghai_api_key or "").strip()
    if token:
        return token

    raise DataSyncError("未配置沧海数据 API Key，无法执行同步。")


def build_canghai_url(base_url: str, token: str) -> str:
    params = {"token": token, "fmt": "json"}
    return f"{base_url}?{urlencode(params)}"


def fetch_json(url: str) -> dict:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "stock-broker/0.1"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def upsert_countries(rows: list[dict]) -> int:
    affected = 0
    for item in rows:
        country_code = str(item.get("country_code") or "").strip()
        country_name = str(item.get("country_name") or "").strip()
        if not country_code or not country_name:
            continue

        record = Country.query.filter_by(country_code=country_code).first()
        if not record:
            record = Country(country_code=country_code)
            db.session.add(record)

        record.country_name = country_name
        record.timezone = normalize_optional_text(item.get("timezone"))
        record.delay = normalize_optional_text(item.get("delay"))
        record.notes = normalize_optional_text(item.get("notes"))
        affected += 1

    db.session.commit()
    return affected


def upsert_exchanges(rows: list[dict]) -> int:
    affected = 0
    country_rows = db.session.execute(select(Country)).scalars().all()
    country_by_code = {row.country_code: row for row in country_rows}

    for item in rows:
        exchange_code = str(item.get("exchange_code") or "").strip()
        exchange_name = str(item.get("exchange_name") or "").strip()
        if not exchange_code or not exchange_name:
            continue

        record = Exchange.query.filter_by(exchange_code=exchange_code).first()
        if not record:
            record = Exchange(exchange_code=exchange_code)
            db.session.add(record)

        country_code = normalize_optional_text(item.get("country_code"))
        country = country_by_code.get(country_code) if country_code else None

        record.exchange_name = exchange_name
        record.exchange_name_short = normalize_optional_text(item.get("exchange_name_short"))
        record.country_code = country_code
        record.country_id = country.id if country else None
        record.currency_code = normalize_optional_text(item.get("currency_code"))
        record.local_open = normalize_optional_text(item.get("local_open"))
        record.local_close = normalize_optional_text(item.get("local_close"))
        record.beijing_open = normalize_optional_text(item.get("beijing_open"))
        record.beijing_close = normalize_optional_text(item.get("beijing_close"))
        record.timezone = normalize_optional_text(item.get("timezone"))
        record.delay = normalize_optional_text(item.get("delay"))
        record.notes = normalize_optional_text(item.get("notes"))
        affected += 1

    db.session.commit()
    return affected


def normalize_optional_text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def log_event(
    *,
    user: User | None,
    event_type: str,
    event_name: str,
    source: str | None,
    target: str | None,
    status: str,
    level: str,
    message: str,
    http_status: int | None = None,
    records_affected: int | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    duration_ms: int | None = None,
) -> EventLog:
    log = EventLog(
        user=user,
        event_type=event_type,
        event_name=event_name,
        source=source,
        target=target,
        status=status,
        level=level,
        message=message,
        http_status=http_status,
        records_affected=records_affected,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
    )
    db.session.add(log)
    db.session.commit()
    return log


def raise_and_log_sync_error(
    *,
    user: User,
    sync_item: str,
    event_name: str,
    started_at: datetime,
    started_perf: float,
    message: str,
    http_status: int | None = None,
) -> None:
    finished_at = datetime.now(timezone.utc)
    duration_ms = int((perf_counter() - started_perf) * 1000)
    log_event(
        user=user,
        event_type="data_sync",
        event_name=event_name,
        source="canghai",
        target=sync_item,
        status="failed",
        level="error",
        message=message,
        http_status=http_status,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
    )
    raise DataSyncError(message)
