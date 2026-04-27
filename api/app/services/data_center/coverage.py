from datetime import date

from sqlalchemy import func

from app.models.exchange import Exchange
from app.models.index_asset import IndexAsset
from app.models.index_daily_bar import IndexDailyBar
from app.models.stock import Stock
from app.models.stock_daily_bar import StockDailyBar
from app.models.trading_calendar_day import TradingCalendarDay

from app.services.data_center.constants import *  # noqa: F403


def get_stock_daily_coverage(exchange_code: str, ticker: str) -> dict:
    normalized_exchange_code = exchange_code.strip().upper()
    normalized_ticker = ticker.strip()
    if not normalized_exchange_code or not normalized_ticker:
        return {"existingDates": [], "latestDate": None, "count": 0}

    query = StockDailyBar.query.filter_by(
        exchange_code=normalized_exchange_code,
        ticker=normalized_ticker,
    )
    rows = query.order_by(StockDailyBar.trade_date.asc(), StockDailyBar.id.asc()).all()
    if not rows:
        rows = (
            StockDailyBar.query.filter(
                StockDailyBar.exchange_code == normalized_exchange_code,
                func.lower(StockDailyBar.ticker) == normalized_ticker.lower(),
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
    normalized_ticker = ticker.strip()
    if not normalized_country_code or not normalized_ticker:
        return {"existingDates": [], "latestDate": None, "count": 0}

    query = IndexDailyBar.query.filter_by(
        country_code=normalized_country_code,
        ticker=normalized_ticker,
    )
    rows = query.order_by(IndexDailyBar.trade_date.asc(), IndexDailyBar.id.asc()).all()
    if not rows:
        rows = (
            IndexDailyBar.query.filter(
                IndexDailyBar.country_code == normalized_country_code,
                func.lower(IndexDailyBar.ticker) == normalized_ticker.lower(),
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


def get_latest_stock_daily_date(stock: Stock) -> date | None:
    latest = (
        StockDailyBar.query.filter_by(exchange_code=stock.exchange_code, ticker=stock.ticker)
        .order_by(StockDailyBar.trade_date.desc(), StockDailyBar.id.desc())
        .first()
    )
    return latest.trade_date if latest and latest.trade_date else None


def get_latest_index_daily_date(index_asset: IndexAsset) -> date | None:
    latest = (
        IndexDailyBar.query.filter_by(
            country_code=index_asset.country_code, ticker=index_asset.ticker
        )
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
