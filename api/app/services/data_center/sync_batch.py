from datetime import date, datetime, timedelta, timezone
from time import perf_counter

from sqlalchemy import and_, func

from app.extensions import db
from app.models.index_asset import IndexAsset
from app.models.index_daily_bar import IndexDailyBar
from app.models.stock import Stock
from app.models.stock_daily_bar import StockDailyBar
from app.models.user import User

from app.services.data_center.constants import *  # noqa: F403
from app.services.data_center.errors import DataSyncError
from app.services.data_center.events import log_event
from app.services.data_center.sync_daily_history import (
    sync_index_daily_history,
    sync_stock_daily_history,
)
from app.services.data_center.time import beijing_today


def batch_sync_stock_daily_history(
    user: User, *, task_id: str | None = None, log_result: bool = True
) -> dict:
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


def batch_sync_index_daily_history(
    user: User, *, task_id: str | None = None, log_result: bool = True
) -> dict:
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
        if latest_trade_date is not None and latest_trade_date < target_end_date
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
        records_affected=int(stock_result.get("recordsAffected", 0))
        + int(index_result.get("recordsAffected", 0)),
    )
    return {
        "status": (
            "success"
            if stock_result.get("status") == "success" and index_result.get("status") == "success"
            else "partial_success"
        ),
        "totalStocks": stock_result.get("totalStocks", 0),
        "totalIndexes": index_result.get("totalIndexes", 0),
        "successCount": int(stock_result.get("successCount", 0))
        + int(index_result.get("successCount", 0)),
        "failedCount": int(stock_result.get("failedCount", 0))
        + int(index_result.get("failedCount", 0)),
        "skippedCount": int(stock_result.get("skippedCount", 0))
        + int(index_result.get("skippedCount", 0)),
        "recordsAffected": int(stock_result.get("recordsAffected", 0))
        + int(index_result.get("recordsAffected", 0)),
        "durationMs": int(stock_result.get("durationMs", 0))
        + int(index_result.get("durationMs", 0)),
        "message": message,
    }
