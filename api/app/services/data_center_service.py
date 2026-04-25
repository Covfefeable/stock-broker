import json
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select

from app.extensions import db
from app.models.country import Country
from app.models.data_source_status import DataSourceStatus
from app.models.event_log import EventLog
from app.models.exchange import Exchange
from app.models.index_asset import IndexAsset
from app.models.index_daily_bar import IndexDailyBar
from app.models.setting import Setting
from app.models.stock import Stock
from app.models.stock_daily_bar import StockDailyBar
from app.models.stock_split import StockSplit
from app.models.trading_calendar_day import TradingCalendarDay
from app.models.user import User
from app.services.event_log_meta import event_log_to_dict, event_types_for_category, sync_event_name, sync_item_label
from app.services.settings_service import get_or_create_settings
from app.services.stock_adjustment import apply_stock_split_adjustments
from app.services.task_center_service import publish_task_event

CANGHAI_COUNTRY_URL = "https://www.tsanghi.com/api/fin/index/country"
CANGHAI_EXCHANGE_URL = "https://www.tsanghi.com/api/fin/stock/exchange"
CANGHAI_SOURCE_KEY = "canghai"
CANGHAI_SOURCE_NAME = "沧海数据"

SYNC_ITEM_COUNTRY_LIST = "country_list"
SYNC_ITEM_EXCHANGE_LIST = "exchange_list"
SYNC_ITEM_STOCK_LIST = "stock_list"
SYNC_ITEM_INDEX_LIST = "index_list"
SYNC_ITEM_TRADING_CALENDAR = "trading_calendar"
SYNC_ITEM_STOCK_DAILY_HISTORY = "stock_daily_history"
SYNC_ITEM_INDEX_DAILY_HISTORY = "index_daily_history"

DATE_MODE_AUTO_FILL = "auto_fill"
DATE_MODE_CUSTOM = "custom"
DEFAULT_FULL_HISTORY_SYNC_START_DATE = "2000-01-01"


def beijing_today() -> date:
    return datetime.now(ZoneInfo("Asia/Shanghai")).date()


def canghai_stock_url(exchange_code: str) -> str:
    return f"https://www.tsanghi.com/api/fin/stock/{exchange_code}/list"


def canghai_index_url(country_code: str) -> str:
    return f"https://www.tsanghi.com/api/fin/index/{country_code}/list"


def canghai_stock_daily_url(exchange_code: str) -> str:
    return f"https://www.tsanghi.com/api/fin/stock/{exchange_code}/daily"


def canghai_stock_split_url(exchange_code: str) -> str:
    return f"https://www.tsanghi.com/api/fin/stock/{exchange_code}/split"


def canghai_trading_calendar_url(exchange_code: str) -> str:
    return f"https://www.tsanghi.com/api/fin/stock/{exchange_code}/market/calendar"


def canghai_index_daily_url(country_code: str) -> str:
    return f"https://www.tsanghi.com/api/fin/index/{country_code}/daily"


class DataSyncError(ValueError):
    pass


def get_data_center_overview_metrics() -> dict:
    stocks_count = Stock.query.count()
    stock_daily_count = StockDailyBar.query.count()
    exchange_count = Exchange.query.count()
    synced_stocks_count = (
        db.session.query(func.count())
        .select_from(
            db.session.query(
                StockDailyBar.exchange_code,
                StockDailyBar.ticker,
            )
            .distinct()
            .subquery()
        )
        .scalar()
        or 0
    )
    synced_indexes_count = (
        db.session.query(func.count())
        .select_from(
            db.session.query(
                IndexDailyBar.country_code,
                IndexDailyBar.ticker,
            )
            .distinct()
            .subquery()
        )
        .scalar()
        or 0
    )

    latest_trade_date = db.session.query(func.max(StockDailyBar.trade_date)).scalar()
    exchange_coverage = list_exchange_stock_coverage()

    return {
        "stocksCount": stocks_count,
        "stockDailyBarsCount": stock_daily_count,
        "exchangeCount": exchange_count,
        "syncedAssetsCount": synced_stocks_count + synced_indexes_count,
        "latestTradeDate": latest_trade_date.isoformat() if latest_trade_date else None,
        "exchangeCoverage": exchange_coverage,
    }


def get_data_source_status_snapshot() -> dict:
    record = DataSourceStatus.query.filter_by(source_key=CANGHAI_SOURCE_KEY).first()
    if not record:
        return {
            "sourceKey": CANGHAI_SOURCE_KEY,
            "sourceName": CANGHAI_SOURCE_NAME,
            "status": "unknown",
            "latencyMs": None,
            "checkedAt": None,
            "httpStatus": None,
            "message": "尚未检测",
        }
    return record.to_dict()


def check_canghai_data_source_status(*, task_id: str | None = None) -> dict:
    started_at = datetime.now(timezone.utc)
    started_perf = perf_counter()
    status = "abnormal"
    http_status: int | None = None
    message = "状态检测失败"

    try:
        token = get_any_canghai_token()
        beijing_today = datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Shanghai")).date()
        check_date = beijing_today - timedelta(days=1)
        request_url = build_canghai_url(
            canghai_stock_daily_url("XNAS"),
            token,
            extra_params={
                "ticker": "TSLA",
                "start_date": check_date.isoformat(),
                "end_date": check_date.isoformat(),
            },
        )
        request = Request(request_url, headers={"Accept": "application/json"})
        with urlopen(request, timeout=20) as response:
            http_status = response.status
            payload = json.loads(response.read().decode("utf-8"))
            status = "normal" if http_status == 200 and int(payload.get("code") or 0) == 200 else "abnormal"
            message = str(payload.get("msg") or "Status check finished")
    except HTTPError as exc:
        http_status = exc.code
        message = f"HTTP {exc.code}"
    except URLError as exc:
        message = f"网络异常：{exc.reason}"
    except DataSyncError as exc:
        message = str(exc)
    except Exception as exc:
        message = f"检测异常：{exc}"

    checked_at = datetime.now(timezone.utc)
    latency_ms = int((perf_counter() - started_perf) * 1000)
    record = DataSourceStatus.query.filter_by(source_key=CANGHAI_SOURCE_KEY).first()
    if not record:
        record = DataSourceStatus(source_key=CANGHAI_SOURCE_KEY, source_name=CANGHAI_SOURCE_NAME)
        db.session.add(record)

    record.status = status
    record.latency_ms = latency_ms
    record.checked_at = checked_at
    record.http_status = http_status
    record.message = message
    db.session.commit()

    log_event(
        user=None,
        task_id=task_id,
        show_in_ui=False,
        event_type="data_source_check",
        event_name="check_canghai_data_source_status",
        source="canghai",
        target=CANGHAI_SOURCE_KEY,
        status="success" if status == "normal" else "failed",
        level="info" if status == "normal" else "warning",
        message=f"{CANGHAI_SOURCE_NAME}状态检测完成：{message}",
        http_status=http_status,
        started_at=started_at,
        finished_at=checked_at,
        duration_ms=latency_ms,
    )

    return record.to_dict()


def list_exchange_stock_coverage() -> list[dict]:
    exchange_rows = Exchange.query.order_by(Exchange.exchange_name.asc(), Exchange.exchange_code.asc()).all()
    if not exchange_rows:
        return []

    total_by_exchange_rows = (
        db.session.query(
            Stock.exchange_code,
            func.count(Stock.id),
        )
        .filter(Stock.exchange_code.isnot(None))
        .group_by(Stock.exchange_code)
        .all()
    )
    total_by_exchange = {exchange_code: total for exchange_code, total in total_by_exchange_rows}

    actual_by_exchange_rows = (
        db.session.query(
            Stock.exchange_code,
            func.count(func.distinct(Stock.id)),
        )
        .join(
            StockDailyBar,
            (Stock.exchange_code == StockDailyBar.exchange_code)
            & (Stock.ticker == StockDailyBar.ticker),
        )
        .filter(Stock.exchange_code.isnot(None))
        .group_by(Stock.exchange_code)
        .all()
    )
    actual_by_exchange = {exchange_code: total for exchange_code, total in actual_by_exchange_rows}

    items: list[dict] = []
    for exchange in exchange_rows:
        total = int(total_by_exchange.get(exchange.exchange_code) or 0)
        if total <= 0:
            continue

        actual = int(actual_by_exchange.get(exchange.exchange_code) or 0)
        percent = round((actual / total) * 100, 2) if total > 0 else 0.0
        items.append(
            {
                "exchangeCode": exchange.exchange_code,
                "exchangeName": exchange.exchange_name_short or exchange.exchange_name,
                "actual": actual,
                "expected": total,
                "percent": percent,
            }
        )

    return items


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
        raise DataSyncError(
            f"未找到交易所 {normalized_exchange_code}，请先完成交易所清单同步。"
        )

    return sync_with_token_guard(
        user=user,
        task_id=task_id,
        sync_item=SYNC_ITEM_STOCK_LIST,
        event_name="sync_stock_list",
        base_url=canghai_stock_url(normalized_exchange_code),
        success_message=f"股票清单同步成功（{normalized_exchange_code}）。",
        upsert_func=lambda rows: upsert_stocks(rows, normalized_exchange_code),
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
        raise DataSyncError(
            f"未找到交易所 {normalized_exchange_code}，请先完成交易所清单同步。"
        )

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
    normalized_ticker = ticker.strip().upper()
    if not normalized_exchange_code:
        raise DataSyncError("同步股票历史日线前请先选择交易所。")
    if not normalized_ticker:
        raise DataSyncError("同步股票历史日线前请先选择股票。")

    stock = Stock.query.filter_by(
        exchange_code=normalized_exchange_code,
        ticker=normalized_ticker,
    ).first()
    if not stock:
        raise DataSyncError(
            f"未找到股票 {normalized_exchange_code}/{normalized_ticker}，请先完成股票清单同步。"
        )

    split_records = sync_stock_splits_for_stock(user, stock)
    extra_params = {"ticker": normalized_ticker, "order": "1"}
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
            f"股票历史日线同步成功（{normalized_exchange_code}/{normalized_ticker}），"
            f"同步送股/拆股事件 {split_records} 条。"
        ),
        upsert_func=lambda rows: upsert_stock_daily_bars(rows, stock),
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
    normalized_ticker = ticker.strip().upper()
    if not normalized_country_code:
        raise DataSyncError("同步指数历史日线前请先选择国家/地区。")
    if not normalized_ticker:
        raise DataSyncError("同步指数历史日线前请先选择指数。")

    index_asset = IndexAsset.query.filter_by(
        country_code=normalized_country_code,
        ticker=normalized_ticker,
    ).first()
    if not index_asset:
        raise DataSyncError(
            f"未找到指数 {normalized_country_code}/{normalized_ticker}，请先完成指数清单同步。"
        )

    extra_params = {"ticker": normalized_ticker, "order": "1"}
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
        success_message=f"指数历史日线同步成功（{normalized_country_code}/{normalized_ticker}）。",
        upsert_func=lambda rows: upsert_index_daily_bars(rows, index_asset),
        extra_params=extra_params,
        log_result=log_result,
    )


def batch_sync_stock_daily_history(user: User, *, task_id: str | None = None, log_result: bool = True) -> dict:
    synced_stock_keys = (
        db.session.query(
            StockDailyBar.exchange_code.label("exchange_code"),
            StockDailyBar.ticker.label("ticker"),
        )
        .distinct()
        .subquery()
    )

    stocks_with_latest = (
        db.session.query(
            Stock,
            func.max(StockDailyBar.trade_date).label("latest_trade_date"),
        )
        .join(
            synced_stock_keys,
            (Stock.exchange_code == synced_stock_keys.c.exchange_code)
            & (Stock.ticker == synced_stock_keys.c.ticker),
        )
        .join(
            StockDailyBar,
            (Stock.exchange_code == StockDailyBar.exchange_code)
            & (Stock.ticker == StockDailyBar.ticker),
        )
        .group_by(Stock.id)
        .order_by(Stock.exchange_code.asc(), Stock.ticker.asc(), Stock.id.asc())
        .all()
    )
    if not stocks_with_latest:
        raise DataSyncError("当前没有已同步过历史日线的股票，无法执行批量补全。")

    target_end_date = beijing_today()

    pending_stocks: list[tuple[Stock, date, date]] = []
    for stock, latest_trade_date in stocks_with_latest:
        if not latest_trade_date:
            continue
        if latest_trade_date < target_end_date:
            pending_stocks.append((stock, latest_trade_date, target_end_date))

    if not pending_stocks:
        if log_result:
            log_event(
                user=user,
                task_id=task_id,
                event_type="data_sync_batch",
                event_name="batch_sync_stock_daily_history",
                source="canghai",
                target=SYNC_ITEM_STOCK_DAILY_HISTORY,
                status="success",
                level="info",
                message=f"批量自动补全完成，共扫描 {len(stocks_with_latest)} 只股票，均已追平北京时间今日，无需发起远程请求。",
                records_affected=0,
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                duration_ms=0,
            )
        return {
            "status": "success",
            "totalStocks": len(stocks_with_latest),
            "successCount": 0,
            "failedCount": 0,
            "skippedCount": len(stocks_with_latest),
            "recordsAffected": 0,
            "durationMs": 0,
        }

    started_at = datetime.now(timezone.utc)
    started_perf = perf_counter()
    total = len(stocks_with_latest)
    success_count = 0
    failed_count = 0
    total_records = 0
    skipped_count = total - len(pending_stocks)
    failed_examples: list[str] = []

    for stock, latest_trade_date, exchange_latest_date in pending_stocks:
        try:
            result = sync_stock_daily_history(
                user=user,
                exchange_code=stock.exchange_code,
                ticker=stock.ticker,
                date_mode=DATE_MODE_CUSTOM,
                start_date=(latest_trade_date + timedelta(days=1)).isoformat(),
                end_date=exchange_latest_date.isoformat(),
                log_result=False,
                task_id=task_id,
            )
            success_count += 1
            records_affected = int(result.get("recordsAffected") or 0)
            total_records += records_affected
        except DataSyncError as exc:
            failed_count += 1
            if len(failed_examples) < 5:
                failed_examples.append(f"{stock.exchange_code}/{stock.ticker}: {exc}")

    finished_at = datetime.now(timezone.utc)
    duration_ms = int((perf_counter() - started_perf) * 1000)

    message = (
        f"批量自动补全完成，共扫描 {total} 只股票，发起补全 {len(pending_stocks)} 只，成功 {success_count}，"
        f"失败 {failed_count}，其中 {skipped_count} 只股票已追平北京时间今日，"
        f"新增或更新 {total_records} 条日线记录。"
    )
    if failed_examples:
        message = f"{message} 失败示例：{'；'.join(failed_examples)}"

    if log_result:
        log_event(
            user=user,
            task_id=task_id,
            event_type="data_sync_batch",
            event_name="batch_sync_stock_daily_history",
            source="canghai",
            target=SYNC_ITEM_STOCK_DAILY_HISTORY,
            status="success" if failed_count == 0 else "partial_success",
            level="info" if failed_count == 0 else "warning",
            message=message,
            records_affected=total_records,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
        )

    return {
        "status": "success" if failed_count == 0 else "partial_success",
        "totalStocks": total,
        "successCount": success_count,
        "failedCount": failed_count,
        "skippedCount": skipped_count,
        "recordsAffected": total_records,
        "durationMs": duration_ms,
    }


def batch_sync_index_daily_history(user: User, *, task_id: str | None = None, log_result: bool = True) -> dict:
    synced_index_keys = (
        db.session.query(
            IndexDailyBar.country_code.label("country_code"),
            IndexDailyBar.ticker.label("ticker"),
        )
        .distinct()
        .subquery()
    )

    indexes_with_latest = (
        db.session.query(
            IndexAsset,
            func.max(IndexDailyBar.trade_date).label("latest_trade_date"),
        )
        .join(
            synced_index_keys,
            and_(
                synced_index_keys.c.country_code == IndexAsset.country_code,
                synced_index_keys.c.ticker == IndexAsset.ticker,
            ),
        )
        .join(
            IndexDailyBar,
            and_(
                IndexDailyBar.country_code == IndexAsset.country_code,
                IndexDailyBar.ticker == IndexAsset.ticker,
            ),
        )
        .group_by(IndexAsset.id)
        .order_by(IndexAsset.country_code.asc(), IndexAsset.ticker.asc())
        .all()
    )

    if not indexes_with_latest:
        raise DataSyncError("当前没有已同步过历史日线的指数，无法执行批量补全。")

    target_end_date = beijing_today()

    pending_indexes = [
        (index_asset, latest_trade_date, target_end_date)
        for index_asset, latest_trade_date in indexes_with_latest
        if latest_trade_date is not None
        and latest_trade_date < target_end_date
    ]

    if not pending_indexes:
        if log_result:
            log_event(
                user=user,
                task_id=task_id,
                event_type="data_sync_batch",
                event_name="batch_sync_index_daily_history",
                source="canghai",
                target=SYNC_ITEM_INDEX_DAILY_HISTORY,
                status="success",
                level="info",
                message=f"批量自动补全完成，共扫描 {len(indexes_with_latest)} 个指数，均已追平北京时间今日，无需发起远程请求。",
                records_affected=0,
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                duration_ms=0,
            )
        return {
            "status": "success",
            "totalIndexes": len(indexes_with_latest),
            "successCount": 0,
            "failedCount": 0,
            "skippedCount": len(indexes_with_latest),
            "recordsAffected": 0,
            "durationMs": 0,
        }

    started_at = datetime.now(timezone.utc)
    started_perf = perf_counter()
    total = len(indexes_with_latest)
    success_count = 0
    failed_count = 0
    skipped_count = total - len(pending_indexes)
    total_records = 0
    failed_examples: list[str] = []

    for index_asset, latest_trade_date, country_latest_date in pending_indexes:
        try:
            result = sync_index_daily_history(
                user=user,
                country_code=index_asset.country_code,
                ticker=index_asset.ticker,
                date_mode=DATE_MODE_CUSTOM,
                start_date=(latest_trade_date + timedelta(days=1)).isoformat(),
                end_date=country_latest_date.isoformat() if country_latest_date else None,
                log_result=False,
                task_id=task_id,
            )
            total_records += int(result.get("recordsAffected") or 0)
            success_count += 1
        except DataSyncError as exc:
            failed_count += 1
            if len(failed_examples) < 5:
                failed_examples.append(f"{index_asset.country_code}/{index_asset.ticker}: {exc}")

    finished_at = datetime.now(timezone.utc)
    duration_ms = int((perf_counter() - started_perf) * 1000)
    message = (
        f"批量自动补全完成，共扫描 {total} 个指数，发起补全 {len(pending_indexes)} 个，成功 {success_count}，"
        f"失败 {failed_count}，其中 {skipped_count} 个指数已追平北京时间今日，新增或更新 {total_records} 条日线记录。"
    )
    if failed_examples:
        message = f"{message} 失败示例：{'；'.join(failed_examples)}"

    if log_result:
        log_event(
            user=user,
            task_id=task_id,
            event_type="data_sync_batch",
            event_name="batch_sync_index_daily_history",
            source="canghai",
            target=SYNC_ITEM_INDEX_DAILY_HISTORY,
            status="success" if failed_count == 0 else "partial_success",
            level="info" if failed_count == 0 else "warning",
            message=message,
            records_affected=total_records,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
        )

    return {
        "status": "success" if failed_count == 0 else "partial_success",
        "totalIndexes": total,
        "successCount": success_count,
        "failedCount": failed_count,
        "skippedCount": skipped_count,
        "recordsAffected": total_records,
        "durationMs": duration_ms,
    }


def batch_sync_stock_and_index_daily_history(user: User, *, task_id: str | None = None) -> dict:
    stock_result: dict[str, Any]
    index_result: dict[str, Any]

    try:
        stock_result = batch_sync_stock_daily_history(user, task_id=task_id, log_result=False)
    except DataSyncError as exc:
        if "当前没有已同步过历史日线的股票" in str(exc):
            stock_result = {
                "status": "success",
                "totalStocks": 0,
                "successCount": 0,
                "failedCount": 0,
                "skippedCount": 0,
                "recordsAffected": 0,
                "durationMs": 0,
            }
        else:
            raise

    try:
        index_result = batch_sync_index_daily_history(user, task_id=task_id, log_result=False)
    except DataSyncError as exc:
        if "当前没有已同步过历史日线的指数" in str(exc):
            index_result = {
                "status": "success",
                "totalIndexes": 0,
                "successCount": 0,
                "failedCount": 0,
                "skippedCount": 0,
                "recordsAffected": 0,
                "durationMs": 0,
            }
        else:
            raise

    if stock_result.get("totalStocks", 0) == 0 and index_result.get("totalIndexes", 0) == 0:
        raise DataSyncError("当前没有已同步过历史日线的股票或指数，无法执行批量补全。")

    message = (
        f"批量同步股票/指数日线完成：股票共 {stock_result.get('totalStocks', 0)} 只，指数共 {index_result.get('totalIndexes', 0)} 个，"
        f"成功 {int(stock_result.get('successCount', 0)) + int(index_result.get('successCount', 0))}，"
        f"失败 {int(stock_result.get('failedCount', 0)) + int(index_result.get('failedCount', 0))}，"
        f"跳过 {int(stock_result.get('skippedCount', 0)) + int(index_result.get('skippedCount', 0))}，"
        f"新增或更新 {int(stock_result.get('recordsAffected', 0)) + int(index_result.get('recordsAffected', 0))} 条记录。"
    )
    log_event(
        user=user,
        task_id=task_id,
        event_type="data_sync_batch",
        event_name="batch_sync_stock_and_index_daily_history",
        source="canghai",
        target=SYNC_ITEM_STOCK_DAILY_HISTORY,
        status=(
            "success"
            if stock_result.get("status") == "success" and index_result.get("status") == "success"
            else "partial_success"
        ),
        level=(
            "info"
            if stock_result.get("status") == "success" and index_result.get("status") == "success"
            else "warning"
        ),
        message=message,
        records_affected=int(stock_result.get("recordsAffected", 0)) + int(index_result.get("recordsAffected", 0)),
    )
    return {
        "status": (
            "success"
            if stock_result.get("status") == "success" and index_result.get("status") == "success"
            else "partial_success"
        ),
        "totalStocks": stock_result.get("totalStocks", 0),
        "totalIndexes": index_result.get("totalIndexes", 0),
        "successCount": int(stock_result.get("successCount", 0)) + int(index_result.get("successCount", 0)),
        "failedCount": int(stock_result.get("failedCount", 0)) + int(index_result.get("failedCount", 0)),
        "skippedCount": int(stock_result.get("skippedCount", 0)) + int(index_result.get("skippedCount", 0)),
        "recordsAffected": int(stock_result.get("recordsAffected", 0)) + int(index_result.get("recordsAffected", 0)),
        "durationMs": int(stock_result.get("durationMs", 0)) + int(index_result.get("durationMs", 0)),
        "message": message,
    }


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
        raise DataSyncError(f"股票送股/拆股信息同步失败（{stock.exchange_code}/{stock.ticker}）。{detail}") from exc
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
        raise DataSyncError(f"股票送股/拆股信息同步失败（{stock.exchange_code}/{stock.ticker}）：上游数据结构不符合预期。")
    return upsert_stock_splits(rows, stock)


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


def list_recent_event_logs(*, offset: int = 0, limit: int = 20, category: str | None = None) -> dict:
    query = EventLog.query.filter(EventLog.show_in_ui.is_(True))
    if category:
        query = query.filter(EventLog.event_type.in_(event_types_for_category(category)))
    rows = (
        query.order_by(EventLog.created_at.desc(), EventLog.id.desc())
        .offset(max(offset, 0))
        .limit(max(limit, 1) + 1)
        .all()
    )
    has_more = len(rows) > limit
    items = rows[:limit]
    return {
        "items": [event_log_to_dict(row) for row in items],
        "hasMore": has_more,
        "nextOffset": offset + len(items),
    }


def list_exchange_options() -> list[dict]:
    rows = (
        Exchange.query.order_by(Exchange.exchange_code.asc(), Exchange.id.asc())
        .all()
    )
    return [
        {
            "label": f"{row.exchange_code} - {row.exchange_name_short or row.exchange_name}",
            "value": row.exchange_code,
            "countryCode": row.country_code,
        }
        for row in rows
    ]


def list_stock_options(exchange_code: str) -> list[dict]:
    normalized_exchange_code = exchange_code.strip().upper()
    if not normalized_exchange_code:
        return []

    latest_date_subquery = (
        db.session.query(
            StockDailyBar.exchange_code.label("exchange_code"),
            StockDailyBar.ticker.label("ticker"),
            func.max(StockDailyBar.trade_date).label("latest_date"),
        )
        .filter(StockDailyBar.exchange_code == normalized_exchange_code)
        .group_by(StockDailyBar.exchange_code, StockDailyBar.ticker)
        .subquery()
    )

    rows = (
        db.session.query(Stock, latest_date_subquery.c.latest_date)
        .outerjoin(
            latest_date_subquery,
            (Stock.exchange_code == latest_date_subquery.c.exchange_code)
            & (Stock.ticker == latest_date_subquery.c.ticker),
        )
        .filter(Stock.exchange_code == normalized_exchange_code)
        .order_by(Stock.ticker.asc(), Stock.id.asc())
        .all()
    )

    items: list[dict] = []
    for stock, latest_date in rows:
        latest_date_text = latest_date.isoformat() if latest_date else None
        label = f"{stock.ticker} - {stock.name}"
        if latest_date_text:
            label = f"{label}（同步至 {latest_date_text}）"
        items.append(
            {
                "label": label,
                "value": stock.ticker,
                "latestDate": latest_date_text,
            }
        )
    return items


def list_index_options(country_code: str) -> list[dict]:
    normalized_country_code = country_code.strip().upper()
    if not normalized_country_code:
        return []

    latest_date_subquery = (
        db.session.query(
            IndexDailyBar.country_code.label("country_code"),
            IndexDailyBar.ticker.label("ticker"),
            func.max(IndexDailyBar.trade_date).label("latest_date"),
        )
        .filter(IndexDailyBar.country_code == normalized_country_code)
        .group_by(IndexDailyBar.country_code, IndexDailyBar.ticker)
        .subquery()
    )

    rows = (
        db.session.query(IndexAsset, latest_date_subquery.c.latest_date)
        .outerjoin(
            latest_date_subquery,
            (IndexAsset.country_code == latest_date_subquery.c.country_code)
            & (IndexAsset.ticker == latest_date_subquery.c.ticker),
        )
        .filter(IndexAsset.country_code == normalized_country_code)
        .order_by(IndexAsset.ticker.asc(), IndexAsset.id.asc())
        .all()
    )

    items: list[dict] = []
    for index_asset, latest_date in rows:
        latest_date_text = latest_date.isoformat() if latest_date else None
        label = f"{index_asset.ticker} - {index_asset.name}"
        if latest_date_text:
            label = f"{label}（同步至 {latest_date_text}）"
        items.append(
            {
                "label": label,
                "value": index_asset.ticker,
                "latestDate": latest_date_text,
            }
        )
    return items


def get_stock_daily_coverage(exchange_code: str, ticker: str) -> dict:
    normalized_exchange_code = exchange_code.strip().upper()
    normalized_ticker = ticker.strip().upper()
    if not normalized_exchange_code or not normalized_ticker:
        return {"existingDates": [], "latestDate": None, "count": 0}

    rows = (
        StockDailyBar.query.filter_by(
            exchange_code=normalized_exchange_code,
            ticker=normalized_ticker,
        )
        .order_by(StockDailyBar.trade_date.asc(), StockDailyBar.id.asc())
        .all()
    )
    dates = [row.trade_date.isoformat() for row in rows if row.trade_date]
    return {
        "existingDates": dates,
        "latestDate": dates[-1] if dates else None,
        "count": len(dates),
    }


def get_index_daily_coverage(country_code: str, ticker: str) -> dict:
    normalized_country_code = country_code.strip().upper()
    normalized_ticker = ticker.strip().upper()
    if not normalized_country_code or not normalized_ticker:
        return {"existingDates": [], "latestDate": None, "count": 0}

    rows = (
        IndexDailyBar.query.filter_by(
            country_code=normalized_country_code,
            ticker=normalized_ticker,
        )
        .order_by(IndexDailyBar.trade_date.asc(), IndexDailyBar.id.asc())
        .all()
    )
    dates = [row.trade_date.isoformat() for row in rows if row.trade_date]
    return {
        "existingDates": dates,
        "latestDate": dates[-1] if dates else None,
        "count": len(dates),
    }


def get_stock_browser_bars(exchange_code: str, ticker: str) -> dict:
    normalized_exchange_code = exchange_code.strip().upper()
    normalized_ticker = ticker.strip().upper()
    if not normalized_exchange_code or not normalized_ticker:
        return {"meta": None, "bars": []}

    stock = Stock.query.filter_by(exchange_code=normalized_exchange_code, ticker=normalized_ticker).first()
    if not stock:
        return {"meta": None, "bars": []}

    rows = (
        StockDailyBar.query.filter_by(exchange_code=normalized_exchange_code, ticker=normalized_ticker)
        .order_by(StockDailyBar.trade_date.desc(), StockDailyBar.id.desc())
        .all()
    )
    bars = apply_stock_split_adjustments([row.to_dict() for row in reversed(rows)], stock.exchange_code, stock.ticker)
    return {
        "meta": {
            "type": "stock",
            "name": stock.name,
            "ticker": stock.ticker,
            "exchangeCode": stock.exchange_code,
            "countryCode": stock.country_code,
            "latestDate": bars[-1]["date"] if bars else None,
            "count": len(bars),
        },
        "bars": bars,
    }


def get_index_browser_bars(country_code: str, ticker: str) -> dict:
    normalized_country_code = country_code.strip().upper()
    normalized_ticker = ticker.strip().upper()
    if not normalized_country_code or not normalized_ticker:
        return {"meta": None, "bars": []}

    index_asset = IndexAsset.query.filter_by(country_code=normalized_country_code, ticker=normalized_ticker).first()
    if not index_asset:
        return {"meta": None, "bars": []}

    rows = (
        IndexDailyBar.query.filter_by(country_code=normalized_country_code, ticker=normalized_ticker)
        .order_by(IndexDailyBar.trade_date.desc(), IndexDailyBar.id.desc())
        .all()
    )
    bars = [row.to_dict() for row in reversed(rows)]
    return {
        "meta": {
            "type": "index",
            "name": index_asset.name,
            "ticker": index_asset.ticker,
            "countryCode": index_asset.country_code,
            "latestDate": bars[-1]["date"] if bars else None,
            "count": len(bars),
        },
        "bars": bars,
    }


def list_country_options() -> list[dict]:
    rows = (
        Country.query.order_by(Country.country_code.asc(), Country.id.asc())
        .all()
    )
    return [
        {
            "label": f"{row.country_code} - {row.country_name}",
            "value": row.country_code,
        }
        for row in rows
    ]


def list_trading_calendar_entries(exchange_code: str, year: int, month: int) -> list[dict]:
    normalized_exchange_code = exchange_code.strip().upper()
    if not normalized_exchange_code:
        return []

    month_start = date(year, month, 1)
    month_end = date(year, month, monthrange(year, month)[1])

    rows = (
        TradingCalendarDay.query.filter(
            TradingCalendarDay.exchange_code == normalized_exchange_code,
            TradingCalendarDay.trade_date >= month_start,
            TradingCalendarDay.trade_date <= month_end,
        )
        .order_by(TradingCalendarDay.trade_date.asc(), TradingCalendarDay.id.asc())
        .all()
    )
    return [row.to_dict() for row in rows]


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


def build_canghai_url(base_url: str, token: str, extra_params: dict[str, str] | None = None) -> str:
    params = {"token": token, "fmt": "json"}
    if extra_params:
        params.update({key: value for key, value in extra_params.items() if value})
    return f"{base_url}?{urlencode(params)}"


def fetch_json(url: str) -> dict:
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "stock-broker/0.1"},
    )
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


def upsert_stocks(rows: list[dict], exchange_code: str) -> int:
    affected = 0
    exchange = Exchange.query.filter_by(exchange_code=exchange_code).first()
    country_rows = db.session.execute(select(Country)).scalars().all()
    country_by_code = {row.country_code: row for row in country_rows}

    for item in rows:
        ticker = str(item.get("ticker") or "").strip()
        name = str(item.get("name") or "").strip()
        if not ticker or not name:
            continue

        record = Stock.query.filter_by(exchange_code=exchange_code, ticker=ticker).first()
        if not record:
            record = Stock(exchange_code=exchange_code, ticker=ticker)
            db.session.add(record)

        country_code = normalize_optional_text(item.get("country_code"))
        country = country_by_code.get(country_code) if country_code else None

        record.name = name
        record.is_active = str(item.get("is_active") or "0").strip() == "1"
        record.exchange_id = exchange.id if exchange else None
        record.country_id = country.id if country else None
        record.country_code = country_code
        record.currency_code = normalize_optional_text(item.get("currency_code"))
        affected += 1

    db.session.commit()
    return affected


def upsert_index_assets(rows: list[dict], country_code: str) -> int:
    affected = 0
    country = Country.query.filter_by(country_code=country_code).first()

    for item in rows:
        ticker = str(item.get("ticker") or "").strip()
        name = str(item.get("name") or "").strip()
        if not ticker or not name:
            continue

        record = IndexAsset.query.filter_by(country_code=country_code, ticker=ticker).first()
        if not record:
            record = IndexAsset(country_code=country_code, ticker=ticker)
            db.session.add(record)

        record.name = name
        record.country_id = country.id if country else None
        affected += 1

    db.session.commit()
    return affected


def upsert_stock_daily_bars(rows: list[dict], stock: Stock) -> int:
    affected = 0
    for item in rows:
        ticker = str(item.get("ticker") or "").strip().upper()
        trade_date_raw = str(item.get("date") or "").strip()
        if not ticker or ticker != stock.ticker or not trade_date_raw:
            continue

        trade_date = date.fromisoformat(trade_date_raw)
        record = StockDailyBar.query.filter_by(
            exchange_code=stock.exchange_code,
            ticker=stock.ticker,
            trade_date=trade_date,
        ).first()
        if not record:
            record = StockDailyBar(
                exchange_code=stock.exchange_code,
                ticker=stock.ticker,
                trade_date=trade_date,
            )
            db.session.add(record)

        record.stock_id = stock.id
        record.open = item.get("open")
        record.high = item.get("high")
        record.low = item.get("low")
        record.close = item.get("close")
        record.volume = int(item["volume"]) if item.get("volume") is not None else None
        affected += 1

    db.session.commit()
    return affected


def upsert_stock_splits(rows: list[dict], stock: Stock) -> int:
    affected = 0
    for item in rows:
        ticker = str(item.get("ticker") or "").strip()
        event_date_raw = str(item.get("date") or "").strip()
        split_factor = parse_positive_decimal(item.get("split_factor"))
        if (
            not ticker
            or ticker.upper() != stock.ticker.upper()
            or not event_date_raw
            or split_factor is None
        ):
            continue

        event_date = date.fromisoformat(event_date_raw)
        record = StockSplit.query.filter_by(
            exchange_code=stock.exchange_code,
            ticker=stock.ticker,
            event_date=event_date,
        ).first()
        if not record:
            record = StockSplit(
                exchange_code=stock.exchange_code,
                ticker=stock.ticker,
                event_date=event_date,
            )
            db.session.add(record)

        record.stock_id = stock.id
        record.split_factor = split_factor
        affected += 1

    db.session.commit()
    return affected


def upsert_index_daily_bars(rows: list[dict], index_asset: IndexAsset) -> int:
    affected = 0
    for item in rows:
        ticker = str(item.get("ticker") or "").strip().upper()
        trade_date_raw = str(item.get("date") or "").strip()
        if not ticker or ticker != index_asset.ticker or not trade_date_raw:
            continue

        trade_date = date.fromisoformat(trade_date_raw)
        record = IndexDailyBar.query.filter_by(
            country_code=index_asset.country_code,
            ticker=index_asset.ticker,
            trade_date=trade_date,
        ).first()
        if not record:
            record = IndexDailyBar(
                country_code=index_asset.country_code,
                ticker=index_asset.ticker,
                trade_date=trade_date,
            )
            db.session.add(record)

        record.index_asset_id = index_asset.id
        record.open = item.get("open")
        record.high = item.get("high")
        record.low = item.get("low")
        record.close = item.get("close")
        record.volume = int(item["volume"]) if item.get("volume") is not None else None
        affected += 1

    db.session.commit()
    return affected


def upsert_trading_calendar_days(rows: list[dict], exchange: Exchange) -> int:
    affected = 0
    for item in rows:
        exchange_code = str(item.get("exchange_code") or "").strip().upper()
        trade_date_raw = str(item.get("date") or "").strip()
        if not exchange_code or exchange_code != exchange.exchange_code or not trade_date_raw:
            continue

        trade_date = date.fromisoformat(trade_date_raw)
        record = TradingCalendarDay.query.filter_by(
            exchange_code=exchange.exchange_code,
            trade_date=trade_date,
        ).first()
        if not record:
            record = TradingCalendarDay(
                exchange_code=exchange.exchange_code,
                trade_date=trade_date,
            )
            db.session.add(record)

        record.exchange_id = exchange.id
        record.status = int(item.get("status") or 0)
        affected += 1

    db.session.commit()
    return affected


def get_latest_stock_daily_date(stock: Stock) -> date | None:
    latest = (
        StockDailyBar.query.filter_by(exchange_code=stock.exchange_code, ticker=stock.ticker)
        .order_by(StockDailyBar.trade_date.desc(), StockDailyBar.id.desc())
        .first()
    )
    return latest.trade_date if latest and latest.trade_date else None


def get_latest_index_daily_date(index_asset: IndexAsset) -> date | None:
    latest = (
        IndexDailyBar.query.filter_by(country_code=index_asset.country_code, ticker=index_asset.ticker)
        .order_by(IndexDailyBar.trade_date.desc(), IndexDailyBar.id.desc())
        .first()
    )
    return latest.trade_date if latest and latest.trade_date else None


def get_latest_trading_calendar_date(exchange: Exchange) -> date | None:
    latest = (
        TradingCalendarDay.query.filter_by(exchange_code=exchange.exchange_code)
        .order_by(TradingCalendarDay.trade_date.desc(), TradingCalendarDay.id.desc())
        .first()
    )
    return latest.trade_date if latest and latest.trade_date else None


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


def log_event(
    *,
    user: User | None,
    task_id: str | None = None,
    show_in_ui: bool = True,
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
        task_id=task_id,
        show_in_ui=show_in_ui,
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
    publish_task_event(log)
    return log


def raise_and_log_sync_error(
    *,
    user: User,
    task_id: str | None = None,
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
        task_id=task_id,
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
