from sqlalchemy import func

from app.extensions import db
from app.models.exchange import Exchange
from app.models.index_daily_bar import IndexDailyBar
from app.models.stock import Stock
from app.models.stock_daily_bar import StockDailyBar

from app.services.data_center.constants import *  # noqa: F403


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


def list_exchange_stock_coverage() -> list[dict]:
    exchange_rows = Exchange.query.order_by(
        Exchange.exchange_name.asc(), Exchange.exchange_code.asc()
    ).all()
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
