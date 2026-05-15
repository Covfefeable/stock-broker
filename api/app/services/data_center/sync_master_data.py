from datetime import timedelta


from app.models.country import Country
from app.models.exchange import Exchange
from app.models.user import User

from app.services.data_center.constants import *  # noqa: F403
from app.services.data_center.canghai_client import (
    canghai_etf_url,
    canghai_index_url,
    canghai_stock_url,
    canghai_trading_calendar_url,
)
from app.services.data_center.coverage import get_latest_trading_calendar_date
from app.services.data_center.errors import DataSyncError
from app.services.data_center.sync_base import sync_with_token_guard
from app.services.data_center.upserts import (
    upsert_countries,
    upsert_exchanges,
    upsert_etfs,
    upsert_index_assets,
    upsert_stocks,
    upsert_trading_calendar_days,
)


def sync_country_list(user: User, *, task_id: str | None = None) -> dict:
    return sync_with_token_guard(
        user=user,
        task_id=task_id,
        sync_item=SYNC_ITEM_COUNTRY_LIST,
        event_name="sync_country_list",
        base_url=CANGHAI_COUNTRY_URL,
        success_message="国家/地区清单同步成功",
        upsert_func=upsert_countries,
    )


def sync_exchange_list(user: User, *, task_id: str | None = None) -> dict:
    return sync_with_token_guard(
        user=user,
        task_id=task_id,
        sync_item=SYNC_ITEM_EXCHANGE_LIST,
        event_name="sync_exchange_list",
        base_url=CANGHAI_EXCHANGE_URL,
        success_message="交易所清单同步成功",
        upsert_func=upsert_exchanges,
    )


def sync_stock_list(user: User, exchange_code: str, *, task_id: str | None = None) -> dict:
    normalized_exchange_code = exchange_code.strip().upper()
    if not normalized_exchange_code:
        raise DataSyncError("同步股票清单前请先选择交易所。")

    exchange = Exchange.query.filter_by(exchange_code=normalized_exchange_code).first()
    if not exchange:
        raise DataSyncError(f"未找到交易所 {normalized_exchange_code}，请先完成交易所清单同步。")

    return sync_with_token_guard(
        user=user,
        task_id=task_id,
        sync_item=SYNC_ITEM_STOCK_LIST,
        event_name="sync_stock_list",
        base_url=canghai_stock_url(normalized_exchange_code),
        success_message=f"股票清单同步成功（{normalized_exchange_code}）。",
        upsert_func=lambda rows: upsert_stocks(rows, normalized_exchange_code),
    )


def sync_etf_list(user: User, exchange_code: str, *, task_id: str | None = None) -> dict:
    normalized_exchange_code = exchange_code.strip().upper()
    if not normalized_exchange_code:
        raise DataSyncError("同步 ETF 清单前请先选择交易所。")

    exchange = Exchange.query.filter_by(exchange_code=normalized_exchange_code).first()
    if not exchange:
        raise DataSyncError(f"未找到交易所 {normalized_exchange_code}，请先完成交易所清单同步。")

    return sync_with_token_guard(
        user=user,
        task_id=task_id,
        sync_item=SYNC_ITEM_ETF_LIST,
        event_name="sync_etf_list",
        base_url=canghai_etf_url(normalized_exchange_code),
        success_message=f"ETF 清单同步成功（{normalized_exchange_code}）。",
        upsert_func=lambda rows: upsert_etfs(rows, normalized_exchange_code),
    )


def sync_index_list(user: User, country_code: str, *, task_id: str | None = None) -> dict:
    normalized_country_code = country_code.strip().upper()
    if not normalized_country_code:
        raise DataSyncError("同步指数清单前请先选择国家/地区。")

    country = Country.query.filter_by(country_code=normalized_country_code).first()
    if not country:
        raise DataSyncError(
            f"未找到国家/地区 {normalized_country_code}，请先完成国家/地区清单同步。"
        )

    return sync_with_token_guard(
        user=user,
        task_id=task_id,
        sync_item=SYNC_ITEM_INDEX_LIST,
        event_name="sync_index_list",
        base_url=canghai_index_url(normalized_country_code),
        success_message=f"指数清单同步成功（{normalized_country_code}）。",
        upsert_func=lambda rows: upsert_index_assets(rows, normalized_country_code),
    )


def sync_trading_calendar(user: User, exchange_code: str, *, task_id: str | None = None) -> dict:
    normalized_exchange_code = exchange_code.strip().upper()
    if not normalized_exchange_code:
        raise DataSyncError("同步交易日历前请先选择交易所。")

    exchange = Exchange.query.filter_by(exchange_code=normalized_exchange_code).first()
    if not exchange:
        raise DataSyncError(f"未找到交易所 {normalized_exchange_code}，请先完成交易所清单同步。")

    extra_params = {"status": "2", "order": "1"}
    latest_trade_date = get_latest_trading_calendar_date(exchange)
    if latest_trade_date:
        extra_params["start_date"] = (latest_trade_date + timedelta(days=1)).isoformat()
    else:
        extra_params["start_date"] = DEFAULT_FULL_HISTORY_SYNC_START_DATE

    return sync_with_token_guard(
        user=user,
        task_id=task_id,
        sync_item=SYNC_ITEM_TRADING_CALENDAR,
        event_name="sync_trading_calendar",
        base_url=canghai_trading_calendar_url(normalized_exchange_code),
        success_message=f"交易日历同步成功（{normalized_exchange_code}）。",
        upsert_func=lambda rows: upsert_trading_calendar_days(rows, exchange),
        extra_params=extra_params,
    )
