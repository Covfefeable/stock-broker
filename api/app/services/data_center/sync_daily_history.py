from datetime import timedelta
from urllib.error import HTTPError, URLError

from sqlalchemy import func

from app.models.index_asset import IndexAsset
from app.models.etf import Etf
from app.models.stock import Stock
from app.models.user import User

from app.services.data_center.constants import *  # noqa: F403
from app.services.data_center.canghai_client import (
    build_canghai_url,
    canghai_etf_daily_url,
    canghai_index_daily_url,
    canghai_stock_dividend_url,
    canghai_stock_daily_url,
    canghai_stock_split_url,
    fetch_json,
)
from app.services.data_center.coverage import (
    get_latest_index_daily_date,
    get_latest_etf_daily_date,
    get_latest_stock_daily_date,
)
from app.services.data_center.errors import DataSyncError
from app.services.data_center.sync_base import sync_with_token_guard
from app.services.data_center.time import beijing_today
from app.services.data_center.tokens import get_user_token
from app.services.data_center.upserts import (
    upsert_index_daily_bars,
    upsert_etf_daily_bars,
    upsert_stock_dividends,
    upsert_stock_daily_bars,
    upsert_stock_splits,
)


def sync_stock_daily_history(
    user: User,
    exchange_code: str,
    ticker: str,
    date_mode: str = DATE_MODE_AUTO_FILL,
    start_date: str | None = None,
    end_date: str | None = None,
    *,
    log_result: bool = True,
    task_id: str | None = None,
) -> dict:
    normalized_exchange_code = exchange_code.strip().upper()
    normalized_ticker = ticker.strip()
    if not normalized_exchange_code:
        raise DataSyncError("同步股票历史日线前请先选择交易所。")
    if not normalized_ticker:
        raise DataSyncError("同步股票历史日线前请先选择股票。")

    stock = Stock.query.filter_by(
        exchange_code=normalized_exchange_code,
        ticker=normalized_ticker,
    ).first()
    if not stock:
        stock = Stock.query.filter(
            Stock.exchange_code == normalized_exchange_code,
            func.lower(Stock.ticker) == normalized_ticker.lower(),
        ).first()
    if not stock:
        raise DataSyncError(
            f"未找到股票 {normalized_exchange_code}/{normalized_ticker}，请先完成股票清单同步。"
        )

    split_records = sync_stock_splits_for_stock(user, stock)
    dividend_records = sync_stock_dividends_for_stock(user, stock)
    extra_params = {"ticker": stock.ticker, "order": "1"}
    if date_mode == DATE_MODE_CUSTOM:
        if start_date:
            extra_params["start_date"] = start_date
        if end_date:
            extra_params["end_date"] = end_date
    else:
        latest_trade_date = get_latest_stock_daily_date(stock)
        if latest_trade_date:
            extra_params["start_date"] = (latest_trade_date + timedelta(days=1)).isoformat()
        else:
            extra_params["start_date"] = DEFAULT_FULL_HISTORY_SYNC_START_DATE
        extra_params["end_date"] = beijing_today().isoformat()

    return sync_with_token_guard(
        user=user,
        task_id=task_id,
        sync_item=SYNC_ITEM_STOCK_DAILY_HISTORY,
        event_name="sync_stock_daily_history",
        base_url=canghai_stock_daily_url(normalized_exchange_code),
        success_message=(
            f"股票历史日线同步成功（{normalized_exchange_code}/{stock.ticker}），"
            f"同步送股/拆股事件 {split_records} 条，现金分红事件 {dividend_records} 条。"
        ),
        upsert_func=lambda rows: upsert_stock_daily_bars(rows, stock),
        extra_params=extra_params,
        log_result=log_result,
    )


def sync_etf_daily_history(
    user: User,
    exchange_code: str,
    ticker: str,
    date_mode: str = DATE_MODE_AUTO_FILL,
    start_date: str | None = None,
    end_date: str | None = None,
    *,
    log_result: bool = True,
    task_id: str | None = None,
) -> dict:
    normalized_exchange_code = exchange_code.strip().upper()
    normalized_ticker = ticker.strip()
    if not normalized_exchange_code:
        raise DataSyncError("同步 ETF 历史日线前请先选择交易所。")
    if not normalized_ticker:
        raise DataSyncError("同步 ETF 历史日线前请先选择 ETF。")

    etf = Etf.query.filter_by(
        exchange_code=normalized_exchange_code,
        ticker=normalized_ticker,
    ).first()
    if not etf:
        etf = Etf.query.filter(
            Etf.exchange_code == normalized_exchange_code,
            func.lower(Etf.ticker) == normalized_ticker.lower(),
        ).first()
    if not etf:
        raise DataSyncError(
            f"未找到 ETF {normalized_exchange_code}/{normalized_ticker}，请先完成 ETF 清单同步。"
        )

    extra_params = {"ticker": etf.ticker, "order": "1"}
    if date_mode == DATE_MODE_CUSTOM:
        if start_date:
            extra_params["start_date"] = start_date
        if end_date:
            extra_params["end_date"] = end_date
    else:
        latest_trade_date = get_latest_etf_daily_date(etf)
        if latest_trade_date:
            extra_params["start_date"] = (latest_trade_date + timedelta(days=1)).isoformat()
        else:
            extra_params["start_date"] = DEFAULT_FULL_HISTORY_SYNC_START_DATE
        extra_params["end_date"] = beijing_today().isoformat()

    return sync_with_token_guard(
        user=user,
        task_id=task_id,
        sync_item=SYNC_ITEM_ETF_DAILY_HISTORY,
        event_name="sync_etf_daily_history",
        base_url=canghai_etf_daily_url(normalized_exchange_code),
        success_message=f"ETF 历史日线同步成功（{normalized_exchange_code}/{etf.ticker}）。",
        upsert_func=lambda rows: upsert_etf_daily_bars(rows, etf),
        extra_params=extra_params,
        log_result=log_result,
    )


def sync_index_daily_history(
    user: User,
    country_code: str,
    ticker: str,
    date_mode: str = DATE_MODE_AUTO_FILL,
    start_date: str | None = None,
    end_date: str | None = None,
    *,
    log_result: bool = True,
    task_id: str | None = None,
) -> dict:
    normalized_country_code = country_code.strip().upper()
    normalized_ticker = ticker.strip()
    if not normalized_country_code:
        raise DataSyncError("同步指数历史日线前请先选择国家/地区。")
    if not normalized_ticker:
        raise DataSyncError("同步指数历史日线前请先选择指数。")

    index_asset = IndexAsset.query.filter_by(
        country_code=normalized_country_code,
        ticker=normalized_ticker,
    ).first()
    if not index_asset:
        index_asset = IndexAsset.query.filter(
            IndexAsset.country_code == normalized_country_code,
            func.lower(IndexAsset.ticker) == normalized_ticker.lower(),
        ).first()
    if not index_asset:
        raise DataSyncError(
            f"未找到指数 {normalized_country_code}/{normalized_ticker}，请先完成指数清单同步。"
        )

    extra_params = {"ticker": index_asset.ticker, "order": "1"}
    if date_mode == DATE_MODE_CUSTOM:
        if start_date:
            extra_params["start_date"] = start_date
        if end_date:
            extra_params["end_date"] = end_date
    else:
        latest_trade_date = get_latest_index_daily_date(index_asset)
        if latest_trade_date:
            extra_params["start_date"] = (latest_trade_date + timedelta(days=1)).isoformat()
        else:
            extra_params["start_date"] = DEFAULT_FULL_HISTORY_SYNC_START_DATE
        extra_params["end_date"] = beijing_today().isoformat()

    return sync_with_token_guard(
        user=user,
        task_id=task_id,
        sync_item=SYNC_ITEM_INDEX_DAILY_HISTORY,
        event_name="sync_index_daily_history",
        base_url=canghai_index_daily_url(normalized_country_code),
        success_message=f"指数历史日线同步成功（{normalized_country_code}/{index_asset.ticker}）。",
        upsert_func=lambda rows: upsert_index_daily_bars(rows, index_asset),
        extra_params=extra_params,
        log_result=log_result,
    )


def sync_stock_splits_for_stock(user: User, stock: Stock) -> int:
    token = get_user_token(user)
    request_url = build_canghai_url(
        canghai_stock_split_url(stock.exchange_code),
        token,
        extra_params={
            "ticker": stock.ticker,
            "start_date": DEFAULT_FULL_HISTORY_SYNC_START_DATE,
            "order": "1",
        },
    )
    try:
        payload = fetch_json(request_url)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
        detail = f" HTTP {exc.code}"
        if body:
            detail = f"{detail}：{body[:240]}"
        raise DataSyncError(
            f"股票送股/拆股信息同步失败（{stock.exchange_code}/{stock.ticker}）。{detail}"
        ) from exc
    except URLError as exc:
        raise DataSyncError(
            f"股票送股/拆股信息同步失败（{stock.exchange_code}/{stock.ticker}），网络请求异常：{exc.reason}"
        ) from exc

    if payload.get("code") != 200:
        raise DataSyncError(
            f"股票送股/拆股信息同步失败（{stock.exchange_code}/{stock.ticker}）："
            f"{payload.get('msg') or '上游接口返回异常'}"
        )
    rows = payload.get("data") or []
    if not isinstance(rows, list):
        raise DataSyncError(
            f"股票送股/拆股信息同步失败（{stock.exchange_code}/{stock.ticker}）：上游数据结构不符合预期。"
        )
    return upsert_stock_splits(rows, stock)


def sync_stock_dividends_for_stock(user: User, stock: Stock) -> int:
    token = get_user_token(user)
    request_url = build_canghai_url(
        canghai_stock_dividend_url(stock.exchange_code),
        token,
        extra_params={
            "ticker": stock.ticker,
            "start_date": DEFAULT_FULL_HISTORY_SYNC_START_DATE,
            "order": "1",
        },
    )
    try:
        payload = fetch_json(request_url)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
        detail = f" HTTP {exc.code}"
        if body:
            detail = f"{detail}：{body[:240]}"
        raise DataSyncError(
            f"股票现金分红信息同步失败（{stock.exchange_code}/{stock.ticker}）。{detail}"
        ) from exc
    except URLError as exc:
        raise DataSyncError(
            f"股票现金分红信息同步失败（{stock.exchange_code}/{stock.ticker}），网络请求异常：{exc.reason}"
        ) from exc

    if payload.get("code") != 200:
        raise DataSyncError(
            f"股票现金分红信息同步失败（{stock.exchange_code}/{stock.ticker}）："
            f"{payload.get('msg') or '上游接口返回异常'}"
        )
    rows = payload.get("data") or []
    if not isinstance(rows, list):
        raise DataSyncError(
            f"股票现金分红信息同步失败（{stock.exchange_code}/{stock.ticker}）：上游数据结构不符合预期。"
        )
    return upsert_stock_dividends(rows, stock)
