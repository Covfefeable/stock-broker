from calendar import monthrange
from datetime import date

from sqlalchemy import func

from app.extensions import db
from app.models.country import Country
from app.models.etf import Etf
from app.models.etf_daily_bar import EtfDailyBar
from app.models.event_log import EventLog
from app.models.exchange import Exchange
from app.models.index_asset import IndexAsset
from app.models.index_daily_bar import IndexDailyBar
from app.models.stock import Stock
from app.models.stock_daily_bar import StockDailyBar
from app.models.trading_calendar_day import TradingCalendarDay
from app.services.event_logs import event_types_for_category, event_log_to_dict

from app.services.data_center.constants import *  # noqa: F403


def list_recent_event_logs(
    *, offset: int = 0, limit: int = 20, category: str | None = None
) -> dict:
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
    rows = Exchange.query.order_by(Exchange.exchange_code.asc(), Exchange.id.asc()).all()
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


def list_etf_options(exchange_code: str) -> list[dict]:
    normalized_exchange_code = exchange_code.strip().upper()
    if not normalized_exchange_code:
        return []

    latest_date_subquery = (
        db.session.query(
            EtfDailyBar.exchange_code.label("exchange_code"),
            EtfDailyBar.ticker.label("ticker"),
            func.max(EtfDailyBar.trade_date).label("latest_date"),
        )
        .filter(EtfDailyBar.exchange_code == normalized_exchange_code)
        .group_by(EtfDailyBar.exchange_code, EtfDailyBar.ticker)
        .subquery()
    )

    rows = (
        db.session.query(Etf, latest_date_subquery.c.latest_date)
        .outerjoin(
            latest_date_subquery,
            (Etf.exchange_code == latest_date_subquery.c.exchange_code)
            & (Etf.ticker == latest_date_subquery.c.ticker),
        )
        .filter(Etf.exchange_code == normalized_exchange_code)
        .order_by(Etf.ticker.asc(), Etf.id.asc())
        .all()
    )

    items: list[dict] = []
    for etf, latest_date in rows:
        latest_date_text = latest_date.isoformat() if latest_date else None
        label = f"{etf.ticker} - {etf.name}"
        if latest_date_text:
            label = f"{label}（同步至 {latest_date_text}）"
        items.append(
            {
                "label": label,
                "value": etf.ticker,
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


def list_country_options() -> list[dict]:
    rows = Country.query.order_by(Country.country_code.asc(), Country.id.asc()).all()
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
